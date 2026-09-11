"""
Per-Short data collection orchestrator.

Processes one Short at a time:
  1. Check scan state → skip if complete
  2. Fetch detailed metadata
  3. Save info.json
  4. Fetch transcript (YouTube API → UNAVAILABLE)
  5. Download video only if needed (for grid)
  6. Extract frames and build preview grid
  7. Clean up temporary files
  8. Update scan state

Transcript failure does NOT block grid generation.
"""

import os
import sys
import time
import traceback

from config import MAX_RETRIES, RETRY_BACKOFF_BASE
from channel import get_video_metadata
from files import (
    make_video_prefix,
    make_folder_name,
    ensure_path_length,
    create_short_dir,
    save_info_json,
    save_transcript,
)
from grid import (
    download_video,
    extract_frames,
    build_preview_grids,
    cleanup_frames,
    cleanup_downloads,
)
from transcript import get_transcript
from state import (
    is_video_complete,
    mark_video_complete,
    mark_video_failed,
    assign_number,
    save_state,
)


def process_short(video_info, channel_dir, state, args, current_idx, total_count):
    """
    Process a single Short: metadata, transcript, preview grid.

    Args:
        video_info: dict with video_id, title, url, duration from listing
        channel_dir: path to channel output directory
        state: scan state dict
        args: parsed CLI arguments
        current_idx: current position (1-based) for display
        total_count: total number of Shorts to process

    Returns:
        dict with collected data for CSV generation, or None if skipped.
    """
    video_id = video_info['video_id']

    # Check if already complete (unless --force)
    if not args.force and is_video_complete(state, video_id):
        return None  # Skip

    # Assign number (preserves existing assignment if resuming)
    video_number = assign_number(state, video_id)
    prefix = make_video_prefix(video_number, video_id)

    print(f"\n[{current_idx}/{total_count}]")
    # Safe print to handle emojis in Windows terminal
    title_str = video_info.get('title', 'Untitled')[:50]
    safe_title = title_str.encode(sys.stdout.encoding or 'utf-8', errors='replace').decode(sys.stdout.encoding or 'utf-8')
    print(f"\n{prefix}_{safe_title}")
    print()

    # ── Step 1: Fetch detailed metadata ────────────────────────────────
    print("    Metadata       ", end="", flush=True)
    metadata = None
    for attempt in range(MAX_RETRIES):
        try:
            metadata = get_video_metadata(video_id)
            break
        except Exception as e:
            if attempt < MAX_RETRIES - 1:
                wait = RETRY_BACKOFF_BASE ** (attempt + 1)
                print(f"RETRY ({wait}s)...", end="", flush=True)
                time.sleep(wait)
            else:
                print(f"FAILED")
                print(f"    [!] Metadata fetch failed: {e}")
                mark_video_failed(state, video_id, video_number, f"metadata: {e}")
                save_state(channel_dir, state)
                return None

    # Add video_number to metadata
    metadata['video_number'] = video_number
    print("DONE")

    # Create folder
    title = metadata.get('title', video_info.get('title', 'Untitled'))
    folder_name = make_folder_name(video_number, video_id, title)
    folder_name = ensure_path_length(
        os.path.join(channel_dir, "shorts"), folder_name, f"{prefix}_preview_grid.jpg"
    )
    short_dir = create_short_dir(channel_dir, folder_name)

    # Save info.json
    info_data = {
        'video_number': video_number,
        'video_id': video_id,
        'title': title,
        'url': metadata.get('url', video_info.get('url', '')),
        'duration_seconds': metadata.get('duration_seconds'),
        'channel_id': metadata.get('channel_id', ''),
        'channel_name': metadata.get('channel_name', ''),
        'timestamp': metadata.get('raw_timestamp'),
        'upload_date': metadata.get('raw_upload_date'),
        'release_timestamp': metadata.get('raw_release_timestamp'),
        'release_date': metadata.get('raw_release_date'),
        'publish_datetime': metadata.get('publish_datetime'),
        'publish_date': metadata.get('publish_date'),
        'publish_time': metadata.get('publish_time'),
    }
    save_info_json(short_dir, prefix, info_data)

    # ── Step 2: Transcript ─────────────────────────────────────────────
    transcript_available = False
    transcript_text = "TRANSCRIPT UNAVAILABLE"

    if not args.skip_transcripts:
        print("    Transcript     ", end="", flush=True)

        # Try YouTube captions (no download needed)
        transcript_text, transcript_available = get_transcript(video_id)
    else:
        print("    Transcript      SKIPPED")

    # ── Step 3: Download video (if needed for grid) ─────────
    video_path = None
    needs_download = not args.skip_grid

    if needs_download:
        print("    Download       ", end="", flush=True)
        for attempt in range(MAX_RETRIES):
            try:
                video_path = download_video(
                    video_id, short_dir,
                    keep_video=args.keep_videos,
                )
                if video_path:
                    print("DONE")
                    break
                else:
                    raise Exception("Download returned no file")
            except Exception as e:
                if attempt < MAX_RETRIES - 1:
                    wait = RETRY_BACKOFF_BASE ** (attempt + 1)
                    print(f"RETRY ({wait}s)...", end="", flush=True)
                    time.sleep(wait)
                else:
                    print("FAILED")
                    print(f"    [!] Video download failed after {MAX_RETRIES} attempts: {e}")

    # Save transcript file (always created, even if UNAVAILABLE)
    save_transcript(short_dir, prefix, transcript_text)
    if not args.skip_transcripts:
        status = "DONE" if transcript_available else "UNAVAILABLE"
        if not transcript_available:
            print(f"    Transcript      {status}")

    # ── Step 4: Frame extraction and grid ──────────────────────────────
    grid_paths = []
    if not args.skip_grid and video_path and os.path.exists(video_path):
        print("    1 FPS Frames   ", end="", flush=True)
        frames_dir = os.path.join(short_dir, "_temp_frames")
        frame_paths = extract_frames(video_path, frames_dir)

        if frame_paths:
            print(f"DONE ({len(frame_paths)} frames)")

            print("    Preview Grid   ", end="", flush=True)
            grid_base = os.path.join(short_dir, f"{prefix}_preview_grid")
            grid_paths = build_preview_grids(frame_paths, grid_base)
            print(f"DONE ({len(grid_paths)} part{'s' if len(grid_paths) != 1 else ''})")

            # Clean up temporary frames
            print("    Cleanup        ", end="", flush=True)
            cleanup_frames(frames_dir)
            print("DONE")
        else:
            print("FAILED")
            print("    Preview Grid    SKIPPED (no frames extracted)")
    elif args.skip_grid:
        print("    Preview Grid    SKIPPED")
    elif not video_path:
        print("    Preview Grid    SKIPPED (no video)")

    # ── Step 5: Cleanup downloads ──────────────────────────────────────
    if video_path:
        cleanup_downloads(short_dir, video_id,
                         keep_video=args.keep_videos)

    # ── Mark complete ─────────────────────────────────────────────────
    mark_video_complete(state, video_id, video_number)
    save_state(channel_dir, state)

    # Build result for CSV generation
    grid_path_str = '; '.join(grid_paths) if grid_paths else ''
    transcript_path = os.path.join(short_dir, f"{prefix}_transcript.txt")

    result = {
        'video_number': video_number,
        'video_id': video_id,
        'title': title,
        'url': metadata.get('url', video_info.get('url', '')),
        'publish_datetime': metadata.get('publish_datetime', ''),
        'publish_date': metadata.get('publish_date', ''),
        'publish_time': metadata.get('publish_time', ''),
        'duration_seconds': metadata.get('duration_seconds', ''),
        'transcript_available': transcript_available,
        'folder_path': short_dir,
        'transcript_path': transcript_path,
        'preview_grid_path': grid_path_str,
    }

    return result

"""
Per-Short data collection orchestrator.

Processes one Short at a time:
  1. Check scan state -> skip if complete
  2. Fetch detailed metadata
  3. Apply date filtering (--start-date / --end-date)
  4. Save info.json
  5. Fetch transcript (YouTube captions only -> UNAVAILABLE)
  6. Download video only if needed (for grid)
  7. Extract frames and build preview grid
  8. Clean up temporary files (guaranteed via try/finally)
  9. Update scan state — only mark complete when ALL outputs succeeded

Transcript failure does NOT block grid generation.
A Short is only marked complete if all enabled outputs exist.
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
from transcript import get_transcript, TranscriptBlocked
from state import (
    is_video_complete,
    mark_video_complete,
    mark_video_failed,
    assign_number,
    save_state,
)


def _is_within_date_range(publish_date, start_date, end_date):
    """
    Check if a publish_date (YYYY-MM-DD string) falls within the given range.
    Returns True if within range or if publish_date is unavailable.
    """
    if not publish_date:
        # Cannot filter without a date — include by default
        return True

    if start_date and publish_date < start_date:
        return False
    if end_date and publish_date > end_date:
        return False
    return True


def process_short(
    video_info,
    channel_dir,
    state,
    args,
    current_idx,
    total_count,
    transcript_delay,
):
    """
    Process a single Short: metadata, transcript, preview grid.

    Args:
        video_info:       dict with video_id, title, url, duration from listing
        channel_dir:      path to channel output directory
        state:            scan state dict
        args:             parsed CLI arguments
        current_idx:      current position (1-based) for display
        total_count:      total number of Shorts to process
        transcript_delay: current adaptive delay in seconds (mutable via return)

    Returns:
        (result_dict | None, transcript_delay)
        result_dict is None if the Short was skipped/failed.
        transcript_delay is the updated delay after this Short.
    """
    video_id = video_info['video_id']

    # Adaptive delay constants
    TRANSCRIPT_MIN_DELAY = 5
    TRANSCRIPT_MAX_DELAY = 120
    TRANSCRIPT_DELAY_STEP = 5

    # Check if already complete (unless --force)
    if not args.force and is_video_complete(state, video_id):
        return None, transcript_delay  # Skip

    # Assign number (preserves existing assignment if resuming)
    video_number = assign_number(state, video_id)
    prefix = make_video_prefix(video_number, video_id)

    print(f"\n[{current_idx}/{total_count}]")
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
                print("FAILED")
                print(f"    [!] Metadata fetch failed: {e}")
                mark_video_failed(state, video_id, video_number, f"metadata: {e}")
                save_state(channel_dir, state)
                return None, transcript_delay

    metadata['video_number'] = video_number
    print("DONE")

    # ── Step 2: Date filtering ─────────────────────────────────────────
    publish_date = metadata.get('publish_date')
    start_date = getattr(args, 'start_date', None)
    end_date = getattr(args, 'end_date', None)

    if not _is_within_date_range(publish_date, start_date, end_date):
        reason = []
        if start_date:
            reason.append(f">= {start_date}")
        if end_date:
            reason.append(f"<= {end_date}")
        print(f"    SKIPPED (date {publish_date} outside range: {', '.join(reason)})")
        # Mark as skipped-by-date so it isn't retried but also isn't "complete"
        state["videos"][video_id] = {
            "video_number": video_number,
            "status": "skipped_date",
        }
        save_state(channel_dir, state)
        return None, transcript_delay

    # ── Step 3: Create folder and save info.json ───────────────────────
    title = metadata.get('title', video_info.get('title', 'Untitled'))
    folder_name = make_folder_name(video_number, video_id, title)
    folder_name = ensure_path_length(
        os.path.join(channel_dir, "shorts"), folder_name, f"{prefix}_preview_grid.jpg"
    )
    short_dir = create_short_dir(channel_dir, folder_name)

    info_data = {
        'video_number': video_number,
        'video_id': video_id,
        'title': title,
        'url': metadata.get('url', video_info.get('url', '')),
        'duration_seconds': metadata.get('duration_seconds'),
        'channel_id': metadata.get('channel_id', ''),
        'channel_name': metadata.get('channel_name', ''),

        'youtube_published_at': metadata.get('youtube_published_at'),

        'timestamp': metadata.get('raw_timestamp'),
        'upload_date': metadata.get('raw_upload_date'),
        'release_timestamp': metadata.get('raw_release_timestamp'),
        'release_date': metadata.get('raw_release_date'),

        'publish_datetime': metadata.get('publish_datetime'),
        'publish_date': metadata.get('publish_date'),
        'publish_time': metadata.get('publish_time'),
        'publish_source': metadata.get('publish_source'),
    }
    save_info_json(short_dir, prefix, info_data)

    # ── Step 4: Transcript (adaptive delay) ───────────────────────────
    transcript_available = False
    transcript_text = "TRANSCRIPT UNAVAILABLE"

    if not args.skip_transcripts:
        # Inter-video delay before requesting transcript
        if transcript_delay > 0:
            time.sleep(transcript_delay)

        while True:
            print("    Transcript     ", end="", flush=True)
            try:
                transcript_text, transcript_available = get_transcript(video_id)

                # Request succeeded (transcript or UNAVAILABLE) — lower delay
                transcript_delay = max(
                    TRANSCRIPT_MIN_DELAY,
                    transcript_delay - TRANSCRIPT_DELAY_STEP,
                )

                if transcript_available:
                    print(f"DONE  (next delay {transcript_delay}s)")
                else:
                    print(f"UNAVAILABLE  (next delay {transcript_delay}s)")
                break

            except TranscriptBlocked:
                save_state(channel_dir, state)

                transcript_delay = min(
                    TRANSCRIPT_MAX_DELAY,
                    transcript_delay + TRANSCRIPT_DELAY_STEP,
                )

                print("IP BLOCKED")
                print(
                    f"    Delay          {transcript_delay}s — retrying same video...",
                    flush=True,
                )

                time.sleep(transcript_delay)

            except Exception as e:
                save_state(channel_dir, state)

                transcript_delay = min(
                    TRANSCRIPT_MAX_DELAY,
                    transcript_delay + TRANSCRIPT_DELAY_STEP,
                )

                print(f"RETRYABLE ERROR: {e}")
                print(
                    f"    Delay          {transcript_delay}s — retrying same video...",
                    flush=True,
                )

                time.sleep(transcript_delay)
    else:
        print("    Transcript      SKIPPED")

    # Save transcript file (always created, even if UNAVAILABLE)
    save_transcript(short_dir, prefix, transcript_text)

    # ── Step 5: Download, extract frames, build grid ───────────────────
    # Track success for completion logic
    grid_required = not args.skip_grid
    grid_success = not grid_required  # True if grid is not required

    video_path = None
    frames_dir = os.path.join(short_dir, "_temp_frames")
    grid_paths = []

    if grid_required:
        try:
            # Download video
            print("    Download       ", end="", flush=True)
            for attempt in range(MAX_RETRIES):
                try:
                    video_path = download_video(video_id, short_dir)
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

            # Extract frames
            if video_path and os.path.exists(video_path):
                print("    1 FPS Frames   ", end="", flush=True)
                frame_paths = extract_frames(video_path, frames_dir)

                if frame_paths:
                    print(f"DONE ({len(frame_paths)} frames)")

                    # Build grids
                    print("    Preview Grid   ", end="", flush=True)
                    grid_base = os.path.join(short_dir, f"{prefix}_preview_grid")
                    grid_paths = build_preview_grids(frame_paths, grid_base)

                    if grid_paths:
                        print(f"DONE ({len(grid_paths)} part{'s' if len(grid_paths) != 1 else ''})")
                        grid_success = True
                    else:
                        print("FAILED")
                else:
                    print("FAILED")
                    print("    Preview Grid    SKIPPED (no frames extracted)")
            else:
                print("    Preview Grid    SKIPPED (no video)")

        finally:
            # Guaranteed cleanup of temporary files
            print("    Cleanup        ", end="", flush=True)
            cleanup_frames(frames_dir)
            if video_path:
                cleanup_downloads(short_dir, video_id,
                                  keep_video=args.keep_videos)
            print("DONE")
    else:
        print("    Preview Grid    SKIPPED")

    # ── Step 6: Mark completion based on actual results ────────────────
    if grid_success:
        mark_video_complete(state, video_id, video_number, {
            'metadata': 'complete',
            'transcript': 'complete' if transcript_available else 'unavailable',
            'grid': 'complete' if grid_required else 'skipped',
        })
    else:
        mark_video_failed(state, video_id, video_number, "grid_failed", {
            'metadata': 'complete',
            'transcript': 'complete' if transcript_available else 'unavailable',
            'grid': 'failed',
        })

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
        'transcript': transcript_text,
        'folder_path': short_dir,
        'transcript_path': transcript_path,
        'preview_grid_path': grid_path_str,
    }

    return result, transcript_delay

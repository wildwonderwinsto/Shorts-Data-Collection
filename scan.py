"""
YouTube Shorts Data Collector — Main Entry Point

Pure data collection tool. Collects metadata, transcripts, and preview grids
for YouTube Shorts. No analysis, scoring, or recommendations.

Usage:
    python scan.py "https://www.youtube.com/@ChannelName"
    python scan.py "@ChannelName" --max-videos 50
    python scan.py "UCxxxxx" --skip-transcripts --output "D:\\MyData"
    python scan.py  (interactive mode)
"""

import os
import sys
import json
import traceback
from datetime import datetime, timezone

from config import parse_args, interactive_prompt
from channel import resolve_channel_url, get_channel_info, list_shorts
from state import load_state, save_state, is_video_complete, assign_number
from files import (
    create_channel_dirs,
    generate_titles_txt,
    generate_titles_csv,
    generate_shorts_csv,
    make_video_prefix,
    make_folder_name,
)
from collector import process_short




def load_existing_results(channel_dir, state):
    """
    Load previously collected video data from info.json files for CSV regeneration.
    """
    results = []
    shorts_dir = os.path.join(channel_dir, "shorts")
    if not os.path.exists(shorts_dir):
        return results

    for video_id, video_state in state.get("videos", {}).items():
        if video_state.get("status") != "complete":
            continue

        video_number = video_state.get("video_number", 0)
        prefix = make_video_prefix(video_number, video_id)

        # Find the folder for this video
        found_dir = None
        for entry in os.listdir(shorts_dir):
            entry_path = os.path.join(shorts_dir, entry)
            if os.path.isdir(entry_path) and entry.startswith(prefix):
                found_dir = entry_path
                break

        if not found_dir:
            continue

        # Load info.json
        info_path = os.path.join(found_dir, f"{prefix}_info.json")
        if not os.path.exists(info_path):
            continue

        try:
            with open(info_path, 'r', encoding='utf-8') as f:
                info = json.load(f)
        except Exception:
            continue

        # Check transcript
        transcript_path = os.path.join(found_dir, f"{prefix}_transcript.txt")
        transcript_available = False
        if os.path.exists(transcript_path):
            with open(transcript_path, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                transcript_available = content != "TRANSCRIPT UNAVAILABLE"

        # Find grid paths
        import glob
        grid_paths = sorted(glob.glob(os.path.join(found_dir, f"{prefix}_preview_grid*.jpg")))
        grid_path_str = '; '.join(grid_paths) if grid_paths else ''

        results.append({
            'video_number': video_number,
            'video_id': video_id,
            'title': info.get('title', ''),
            'url': info.get('url', ''),
            'publish_datetime': info.get('publish_datetime', ''),
            'publish_date': info.get('publish_date', ''),
            'publish_time': info.get('publish_time', ''),
            'duration_seconds': info.get('duration_seconds', ''),
            'transcript_available': transcript_available,
            'folder_path': found_dir,
            'transcript_path': transcript_path,
            'preview_grid_path': grid_path_str,
        })

    # Sort by video_number
    results.sort(key=lambda x: x['video_number'])
    return results


def main():
    """Main entry point."""
    # Parse arguments or run interactive prompt
    if len(sys.argv) <= 1:
        args = interactive_prompt()
    else:
        args = parse_args()

    if not args.channel_url:
        print("Error: No channel URL provided.")
        sys.exit(1)

    print()
    print("=" * 60)
    print("   YOUTUBE SHORTS DATA COLLECTOR")
    print("=" * 60)

    # ── Resolve channel ───────────────────────────────────────────────
    print(f"\nResolving channel: {args.channel_url}")
    shorts_url, channel_ident = resolve_channel_url(args.channel_url)
    print(f"Shorts URL: {shorts_url}")

    # Get channel info
    try:
        channel_info = get_channel_info(shorts_url)
    except Exception as e:
        print(f"\nError: Could not access channel: {e}")
        print("Please check the URL and try again.")
        sys.exit(1)

    channel_name = channel_info['channel_name']
    channel_id = channel_info['channel_id']
    print(f"Channel: {channel_name}")
    print(f"Channel ID: {channel_id}")

    # ── Create output directories ────────────────────────────────────
    channel_dir = create_channel_dirs(args.output, channel_name)
    print(f"Output: {channel_dir}")

    # ── Load scan state ──────────────────────────────────────────────
    state = load_state(channel_dir)
    state['channel_id'] = channel_id
    state['channel_name'] = channel_name

    # ── List all Shorts ──────────────────────────────────────────────
    try:
        shorts = list_shorts(shorts_url, max_videos=args.max_videos)
    except Exception as e:
        print(f"\nError: Could not fetch Shorts list: {e}")
        sys.exit(1)

    if not shorts:
        print("\nNo Shorts found. Exiting.")
        sys.exit(0)

    state['total_shorts_found'] = len(shorts)

    # Date filtering will occur during processing (after metadata fetch).

    # ── Determine which Shorts need processing ───────────────────────
    if args.force:
        to_process = shorts
        print(f"\n--force: Will reprocess all {len(to_process)} Shorts.")
    else:
        to_process = [s for s in shorts if not is_video_complete(state, s['video_id'])]
        already_done = len(shorts) - len(to_process)
        if already_done > 0:
            print(f"\nSkipping {already_done} already-completed Shorts.")
        print(f"Shorts to process: {len(to_process)}")

    if not to_process:
        print("\nAll Shorts are already collected. Nothing to do.")
        # Still regenerate CSVs with existing data
        all_results = load_existing_results(channel_dir, state)
        if all_results:
            generate_titles_txt(channel_dir, all_results)
            generate_titles_csv(channel_dir, all_results)
            generate_shorts_csv(channel_dir, all_results)
            print("CSV files updated.")
        sys.exit(0)

    # ── Assign numbers to all Shorts (preserving existing) ───────────
    # First assign numbers to already-known videos to preserve ordering
    for s in shorts:
        assign_number(state, s['video_id'])
    save_state(channel_dir, state)

    # ── Process each Short ───────────────────────────────────────────
    print(f"\nStarting scan of {len(to_process)} Shorts...")
    print(f"{'=' * 60}")

    new_results = []
    total = len(to_process)

    for idx, short_info in enumerate(to_process, 1):
        try:
            result = process_short(short_info, channel_dir, state, args, idx, total)
            if result:
                new_results.append(result)
        except KeyboardInterrupt:
            print("\n\n[!] Scan interrupted by user. Progress saved.")
            save_state(channel_dir, state)
            break
        except Exception as e:
            print(f"\n[!] Unexpected error processing {short_info['video_id']}: {e}")
            traceback.print_exc()
            video_number = assign_number(state, short_info['video_id'])
            from state import mark_video_failed
            mark_video_failed(state, short_info['video_id'], video_number, str(e))
            save_state(channel_dir, state)
            continue

    # ── Generate output files ────────────────────────────────────────
    print(f"\n{'=' * 60}")
    print("\nGenerating output files...")

    # Collect ALL results (existing + new) for complete CSVs
    all_results = load_existing_results(channel_dir, state)

    # Sort by video_number (oldest first)
    all_results.sort(key=lambda x: x['video_number'])

    if all_results:
        titles_txt_path = generate_titles_txt(channel_dir, all_results)
        titles_csv_path = generate_titles_csv(channel_dir, all_results)
        shorts_csv_path = generate_shorts_csv(channel_dir, all_results)

        print(f"  titles.txt    — {len(all_results)} titles")
        print(f"  titles.csv    — {len(all_results)} rows")
        print(f"  shorts.csv    — {len(all_results)} rows")

    save_state(channel_dir, state)

    # ── Summary ──────────────────────────────────────────────────────
    completed = len(state.get('completed_video_ids', []))
    failed = len(state.get('failed_video_ids', {}))

    print(f"\n{'=' * 60}")
    print(f"  SCAN COMPLETE")
    print(f"{'=' * 60}")
    print(f"  Channel:     {channel_name}")
    print(f"  Completed:   {completed}")
    if failed:
        print(f"  Failed:      {failed}")
    print(f"  Output:      {channel_dir}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()

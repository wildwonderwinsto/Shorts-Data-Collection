"""
Configuration constants and CLI argument parsing.
Pure data collection settings — no analysis, scoring, or recommendations.
"""

import argparse
import os
import sys

# ── Grid settings ──────────────────────────────────────────────────────────
GRID_COLUMNS = 5
MAX_FRAMES_PER_GRID_PART = 30  # Split grids before construction to control memory
JPEG_QUALITY = 95
TIMESTAMP_FONT_SIZE = 28
TIMESTAMP_PADDING = 36  # pixels below each frame for timestamp label

# ── Video settings ─────────────────────────────────────────────────────────
PREFERRED_HEIGHT = 1920
PREFERRED_WIDTH = 1080
MAX_SHORT_DURATION = 180  # safety net — Shorts are typically ≤60s, YouTube allows up to 3 min

# ── Temporary file behaviour ──────────────────────────────────────────────
KEEP_RAW_VIDEOS = False

# ── Retry settings ────────────────────────────────────────────────────────
MAX_RETRIES = 3
RETRY_BACKOFF_BASE = 2  # seconds; exponential: 2, 4, 8

# ── Default output ────────────────────────────────────────────────────────
DEFAULT_OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "YouTubeResearch")


def parse_args(argv=None):
    """Parse command-line arguments. Returns namespace."""
    parser = argparse.ArgumentParser(
        prog="scan.py",
        description="YouTube Shorts Data Collector — collect metadata, transcripts, and preview grids.",
    )

    parser.add_argument(
        "channel_url",
        nargs="?",
        default=None,
        help="YouTube channel URL, @handle, or channel ID",
    )

    parser.add_argument(
        "--max-videos",
        type=int,
        default=None,
        help="Maximum number of Shorts to process",
    )
    parser.add_argument(
        "--start-date",
        type=str,
        default=None,
        help="Only include Shorts published on or after this date (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--end-date",
        type=str,
        default=None,
        help="Only include Shorts published on or before this date (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--skip-transcripts",
        action="store_true",
        default=False,
        help="Skip transcript collection",
    )
    parser.add_argument(
        "--skip-grid",
        action="store_true",
        default=False,
        help="Skip preview grid generation",
    )
    parser.add_argument(
        "--keep-videos",
        action="store_true",
        default=False,
        help="Keep downloaded video files after processing",
    )

    parser.add_argument(
        "--force",
        action="store_true",
        default=False,
        help="Reprocess all Shorts regardless of scan state",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=DEFAULT_OUTPUT_DIR,
        help=f"Output directory (default: {DEFAULT_OUTPUT_DIR})",
    )

    args = parser.parse_args(argv)
    return args


def interactive_prompt():
    """Run interactive prompts when no CLI arguments are provided."""
    print()
    print("=" * 60)
    print("   YOUTUBE SHORTS DATA COLLECTOR")
    print("=" * 60)
    print()

    channel_url = input("Paste YouTube channel URL, @handle, or channel ID:\n> ").strip()
    if not channel_url:
        print("No channel provided. Exiting.")
        sys.exit(1)

    print()
    max_videos_str = input("Maximum number of Shorts? (Press Enter for ALL):\n> ").strip()
    max_videos = int(max_videos_str) if max_videos_str else None

    print()
    output_dir = input(f"Output folder? (Press Enter for default: {DEFAULT_OUTPUT_DIR}):\n> ").strip()
    if not output_dir:
        output_dir = DEFAULT_OUTPUT_DIR

    print()
    skip_transcripts_str = input("Skip transcripts? (y/N):\n> ").strip().lower()
    skip_transcripts = skip_transcripts_str in ("y", "yes")

    print()
    skip_grid_str = input("Skip preview grids? (y/N):\n> ").strip().lower()
    skip_grid = skip_grid_str in ("y", "yes")

    # Build a namespace matching parse_args output
    args = argparse.Namespace(
        channel_url=channel_url,
        max_videos=max_videos,
        start_date=None,
        end_date=None,
        skip_transcripts=skip_transcripts,
        skip_grid=skip_grid,
        keep_videos=False,

        force=False,
        output=output_dir,
    )
    return args

"""
Frame extraction via FFmpeg and preview grid assembly via Pillow.

Key design decisions:
  - Extract exactly 1 frame per second using FFmpeg (fps=1)
  - Use native resolution (prefer 1080x1920) — no downscaling
  - Split grids BEFORE construction at MAX_FRAMES_PER_GRID_PART = 30
  - Build and save one grid part at a time, then release from memory
  - Timestamp labels drawn BELOW each frame, not overlaid on content
  - Delete temporary frame files after grid creation
"""

import glob
import math
import os
import shutil
import subprocess
import sys

from PIL import Image, ImageDraw, ImageFont

from config import (
    GRID_COLUMNS,
    JPEG_QUALITY,
    MAX_FRAMES_PER_GRID_PART,
    TIMESTAMP_FONT_SIZE,
    TIMESTAMP_PADDING,
)


def _get_font(size=TIMESTAMP_FONT_SIZE):
    """Get a clean font for timestamp labels. Falls back to default."""
    # Try common Windows fonts
    font_paths = [
        "C:/Windows/Fonts/consola.ttf",    # Consolas (monospace, clean)
        "C:/Windows/Fonts/arial.ttf",       # Arial
        "C:/Windows/Fonts/segoeui.ttf",     # Segoe UI
    ]
    for fp in font_paths:
        if os.path.exists(fp):
            try:
                return ImageFont.truetype(fp, size)
            except Exception:
                continue
    # Fallback to Pillow default
    try:
        return ImageFont.truetype("arial.ttf", size)
    except Exception:
        return ImageFont.load_default()


def extract_frames(video_path, output_dir):
    """
    Extract 1 frame per second from video using FFmpeg.

    Args:
        video_path: Path to the video file
        output_dir: Directory to save extracted frames

    Returns:
        List of frame file paths sorted by timestamp, or empty list on failure.
    """
    os.makedirs(output_dir, exist_ok=True)

    frame_pattern = os.path.join(output_dir, "frame_%04d.jpg")

    cmd = [
        "ffmpeg",
        "-i", video_path,
        "-vf", "fps=1",
        "-q:v", "2",        # High quality JPEG
        "-y",                # Overwrite
        frame_pattern,
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,  # 5 minute timeout
        )
        if result.returncode != 0:
            print(f"    [!] FFmpeg frame extraction failed: {result.stderr[:500]}")
            return []
    except FileNotFoundError:
        print("    [!] FFmpeg not found. Please install FFmpeg and add it to PATH.")
        return []
    except subprocess.TimeoutExpired:
        print("    [!] FFmpeg frame extraction timed out.")
        return []

    # Collect and sort frame files
    frames = sorted(glob.glob(os.path.join(output_dir, "frame_*.jpg")))
    return frames


def build_preview_grids(frame_paths, output_path_base):
    """
    Build high-resolution preview grid(s) from extracted frames.

    Splits into multiple parts if frame count exceeds MAX_FRAMES_PER_GRID_PART.
    Each part is built, saved, and released from memory independently.

    Args:
        frame_paths: Sorted list of frame image paths
        output_path_base: Base path without extension, e.g. "0001_abc123_preview_grid"

    Returns:
        List of saved grid file paths.
    """
    if not frame_paths:
        return []

    total_frames = len(frame_paths)
    num_parts = math.ceil(total_frames / MAX_FRAMES_PER_GRID_PART)
    font = _get_font()

    saved_paths = []

    for part_idx in range(num_parts):
        start = part_idx * MAX_FRAMES_PER_GRID_PART
        end = min(start + MAX_FRAMES_PER_GRID_PART, total_frames)
        part_frames = frame_paths[start:end]

        if not part_frames:
            continue

        # Determine output filename
        if num_parts == 1:
            grid_path = output_path_base + ".jpg"
        else:
            grid_path = f"{output_path_base}_part{part_idx + 1:02d}.jpg"

        # Build this part
        _build_single_grid(part_frames, grid_path, start, font)
        saved_paths.append(grid_path)

        print(f"    Saved grid: {os.path.basename(grid_path)}")

    return saved_paths


def _build_single_grid(frame_paths, output_path, time_offset, font):
    """
    Build and save a single grid image from a batch of frames.

    Args:
        frame_paths: List of frame image paths for this grid part
        output_path: Where to save the grid JPEG
        time_offset: The starting second index (for timestamp labels)
        font: PIL ImageFont for timestamps
    """
    if not frame_paths:
        return

    # Read the first frame to get dimensions
    with Image.open(frame_paths[0]) as sample:
        frame_w, frame_h = sample.size

    cols = GRID_COLUMNS
    num_frames = len(frame_paths)
    rows = math.ceil(num_frames / cols)

    # Cell dimensions: frame + padding below for timestamp
    cell_w = frame_w
    cell_h = frame_h + TIMESTAMP_PADDING

    # Total grid dimensions
    grid_w = cols * cell_w
    grid_h = rows * cell_h

    # Create grid image (white background)
    grid_img = Image.new('RGB', (grid_w, grid_h), color=(255, 255, 255))
    draw = ImageDraw.Draw(grid_img)

    for i, frame_path in enumerate(frame_paths):
        row = i // cols
        col = i % cols

        x = col * cell_w
        y = row * cell_h

        # Paste the frame
        try:
            with Image.open(frame_path) as frame:
                # Resize only if frame dimensions don't match the first frame
                if frame.size != (frame_w, frame_h):
                    frame = frame.resize((frame_w, frame_h), Image.LANCZOS)
                grid_img.paste(frame, (x, y))
        except Exception as e:
            print(f"    [!] Failed to paste frame {frame_path}: {e}")
            continue

        # Draw timestamp below the frame
        second = time_offset + i
        minutes = second // 60
        secs = second % 60
        timestamp = f"{minutes:02d}:{secs:02d}"

        # Center the timestamp text under the frame
        try:
            bbox = font.getbbox(timestamp)
            text_w = bbox[2] - bbox[0]
        except AttributeError:
            text_w = len(timestamp) * (TIMESTAMP_FONT_SIZE // 2)

        text_x = x + (frame_w - text_w) // 2
        text_y = y + frame_h + 4  # 4px padding from bottom of frame

        draw.text((text_x, text_y), timestamp, fill=(0, 0, 0), font=font)

    # Save with high quality
    grid_img.save(output_path, 'JPEG', quality=JPEG_QUALITY, optimize=True)

    # Explicitly release memory
    del draw
    del grid_img


def cleanup_frames(frames_dir):
    """Delete the temporary frames directory and all its contents."""
    if os.path.exists(frames_dir):
        try:
            shutil.rmtree(frames_dir)
        except Exception as e:
            print(f"    [!] Failed to clean up frames directory: {e}")


def download_video(video_id, output_dir, keep_video=False):
    """
    Download a Short temporarily for frame extraction.

    Prefers native 1080x1920 or better.
    Returns: video_path to downloaded file, or None on failure.
    """
    import yt_dlp

    url = f"https://www.youtube.com/shorts/{video_id}"
    os.makedirs(output_dir, exist_ok=True)

    video_path = os.path.join(output_dir, f"{video_id}_video.mp4")

    # Download best video+audio merged, prefer 1080p+
    ydl_opts = {
        'format': 'bestvideo[height>=1080][ext=mp4]+bestaudio[ext=m4a]/bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        'outtmpl': os.path.join(output_dir, f"{video_id}_video.%(ext)s"),
        'quiet': True,
        'no_warnings': True,
        'merge_output_format': 'mp4',
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
    except Exception as e:
        print(f"    [!] Video download failed: {e}")
        return None

    # Find the actual downloaded file (extension may vary)
    import glob as g
    video_files = g.glob(os.path.join(output_dir, f"{video_id}_video.*"))
    actual_video = None
    for vf in video_files:
        if os.path.isfile(vf):
            actual_video = vf
            break

    return actual_video


def cleanup_downloads(output_dir, video_id, keep_video=False):
    """Remove temporary video files after processing."""
    import glob as g

    if not keep_video:
        for f in g.glob(os.path.join(output_dir, f"{video_id}_video.*")):
            try:
                os.remove(f)
            except Exception:
                pass


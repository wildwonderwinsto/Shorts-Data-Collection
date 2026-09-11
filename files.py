"""
File and folder naming, sanitization, and CSV/TXT generation.
Handles Windows filename restrictions and path length limits.
"""

import csv
import json
import os
import re


# Characters forbidden in Windows filenames
_UNSAFE_CHARS = re.compile(r'[\\/:*?"<>|]')
# Collapse multiple underscores / spaces
_MULTI_UNDERSCORE = re.compile(r'_{2,}')
_MULTI_SPACE = re.compile(r'\s+')


def sanitize_filename(name, max_length=80):
    """
    Make a string safe for use as a Windows filename component.
    Replaces unsafe characters, collapses whitespace, and truncates.
    """
    name = _UNSAFE_CHARS.sub('_', name)
    name = _MULTI_SPACE.sub(' ', name)
    name = name.strip('. _')
    # Replace spaces with underscores for cleaner folder names
    name = name.replace(' ', '_')
    name = _MULTI_UNDERSCORE.sub('_', name)
    # Truncate to max_length
    if len(name) > max_length:
        name = name[:max_length].rstrip('_')
    return name


def make_video_prefix(video_number, video_id):
    """Create the standard prefix like '0001_dQw4w9WgXcQ'."""
    return f"{video_number:04d}_{video_id}"


def make_folder_name(video_number, video_id, title):
    """Create the Short's folder name like '0001_dQw4w9WgXcQ_Why_Ants_Never_Get_Stuck'."""
    prefix = make_video_prefix(video_number, video_id)
    safe_title = sanitize_filename(title, max_length=60)
    folder_name = f"{prefix}_{safe_title}" if safe_title else prefix
    return folder_name


def ensure_path_length(base_dir, folder_name, filename):
    """
    Ensure the full path stays within Windows MAX_PATH (260 chars).
    Truncates the folder name (title portion only) if needed.
    """
    full_path = os.path.join(base_dir, folder_name, filename)
    if len(full_path) <= 255:
        return folder_name

    # Find how much we need to trim
    overhead = len(os.path.join(base_dir, "", filename)) + 1  # +1 for separator
    max_folder_len = 255 - overhead
    if max_folder_len < 20:
        max_folder_len = 20  # absolute minimum
    return folder_name[:max_folder_len].rstrip('_')


def create_channel_dirs(output_dir, channel_name):
    """Create the channel directory structure. Returns the channel root path."""
    safe_channel = sanitize_filename(channel_name, max_length=80)
    channel_dir = os.path.join(output_dir, safe_channel)
    shorts_dir = os.path.join(channel_dir, "shorts")
    os.makedirs(shorts_dir, exist_ok=True)
    return channel_dir


def create_short_dir(channel_dir, folder_name):
    """Create the individual Short's directory. Returns its path."""
    short_dir = os.path.join(channel_dir, "shorts", folder_name)
    os.makedirs(short_dir, exist_ok=True)
    return short_dir


def save_info_json(short_dir, prefix, info_data):
    """Save the raw metadata JSON for a Short."""
    path = os.path.join(short_dir, f"{prefix}_info.json")
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(info_data, f, indent=2, ensure_ascii=False, default=str)
    return path


def save_transcript(short_dir, prefix, transcript_text):
    """Save the transcript text file for a Short."""
    path = os.path.join(short_dir, f"{prefix}_transcript.txt")
    with open(path, 'w', encoding='utf-8') as f:
        f.write(transcript_text)
    return path


def generate_titles_txt(channel_dir, videos):
    """
    Generate titles.txt with format:
    0001 - Title Here
    0002 - Another Title
    """
    path = os.path.join(channel_dir, "titles.txt")
    with open(path, 'w', encoding='utf-8') as f:
        for v in videos:
            f.write(f"{v['video_number']:04d} - {v['title']}\n")
    return path


def generate_titles_csv(channel_dir, videos):
    """
    Generate titles.csv with columns:
    video_number, video_id, title, publish_datetime, publish_date, publish_time, duration_seconds, url
    """
    path = os.path.join(channel_dir, "titles.csv")
    fieldnames = [
        'video_number', 'video_id', 'title', 'publish_datetime',
        'publish_date', 'publish_time', 'duration_seconds', 'url'
    ]
    with open(path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for v in videos:
            writer.writerow({
                'video_number': f"{v['video_number']:04d}",
                'video_id': v['video_id'],
                'title': v['title'],
                'publish_datetime': v.get('publish_datetime', ''),
                'publish_date': v.get('publish_date', ''),
                'publish_time': v.get('publish_time', ''),
                'duration_seconds': v.get('duration_seconds', ''),
                'url': v['url'],
            })
    return path


def generate_shorts_csv(channel_dir, videos):
    """
    Generate master CSV containing metadata AND full transcript.
    """
    path = os.path.join(channel_dir, "shorts.csv")

    fieldnames = [
        'video_number',
        'video_id',
        'title',
        'url',
        'publish_datetime',
        'publish_date',
        'publish_time',
        'duration_seconds',
        'transcript_available',
        'transcript',
        'folder_path',
        'transcript_path',
        'preview_grid_path',
    ]

    with open(
        path,
        'w',
        encoding='utf-8-sig',
        newline=''
    ) as f:

        writer = csv.DictWriter(
            f,
            fieldnames=fieldnames,
            quoting=csv.QUOTE_MINIMAL
        )

        writer.writeheader()

        for v in videos:
            writer.writerow({
                'video_number':
                    f"{v['video_number']:04d}",

                'video_id':
                    v['video_id'],

                'title':
                    v['title'],

                'url':
                    v['url'],

                'publish_datetime':
                    v.get('publish_datetime', ''),

                'publish_date':
                    v.get('publish_date', ''),

                'publish_time':
                    v.get('publish_time', ''),

                'duration_seconds':
                    v.get('duration_seconds', ''),

                'transcript_available':
                    v.get('transcript_available', False),

                'transcript':
                    v.get(
                        'transcript',
                        'TRANSCRIPT UNAVAILABLE'
                    ),

                'folder_path':
                    v.get('folder_path', ''),

                'transcript_path':
                    v.get('transcript_path', ''),

                'preview_grid_path':
                    v.get('preview_grid_path', ''),
            })

    return path


def generate_all_shorts_txt(channel_dir, videos):
    """
    Create one easy-to-copy text file containing all collected Shorts data.
    """
    path = os.path.join(channel_dir, "ALL_SHORTS_DATA.txt")

    with open(path, "w", encoding="utf-8") as f:
        for v in sorted(videos, key=lambda x: x["video_number"]):

            number = f"{v['video_number']:04d}"

            f.write("=" * 70 + "\n")
            f.write(f"SHORT {number}\n")
            f.write("=" * 70 + "\n\n")

            f.write(f"VIDEO ID: {v.get('video_id', '')}\n")
            f.write(f"TITLE: {v.get('title', '')}\n")
            f.write(f"URL: {v.get('url', '')}\n")

            f.write(
                f"PUBLISH DATE: "
                f"{v.get('publish_date') or 'UNAVAILABLE'}\n"
            )

            f.write(
                f"PUBLISH TIME: "
                f"{v.get('publish_time') or 'UNAVAILABLE'}\n"
            )

            f.write(
                f"PUBLISH DATETIME: "
                f"{v.get('publish_datetime') or 'UNAVAILABLE'}\n"
            )

            f.write(
                f"DURATION: "
                f"{v.get('duration_seconds') or 'UNAVAILABLE'} seconds\n"
            )

            f.write("\nTRANSCRIPT:\n")

            transcript = v.get(
                "transcript",
                "TRANSCRIPT UNAVAILABLE"
            )

            if not transcript:
                transcript = "TRANSCRIPT UNAVAILABLE"

            f.write(transcript.strip() + "\n")

            f.write("\nPREVIEW GRID:\n")

            grid_paths = v.get("preview_grid_path", "")

            if grid_paths:
                for grid_path in grid_paths.split(";"):
                    grid_path = grid_path.strip()

                    if not grid_path:
                        continue

                    try:
                        relative = os.path.relpath(
                            grid_path,
                            channel_dir
                        )
                    except ValueError:
                        relative = grid_path

                    f.write(relative + "\n")
            else:
                f.write("UNAVAILABLE\n")

            f.write("\n\n")

    return path


def generate_all_shorts_md(channel_dir, videos):
    """
    Create a Markdown version with clickable/displayable preview grids.
    """
    path = os.path.join(channel_dir, "ALL_SHORTS_DATA.md")

    with open(path, "w", encoding="utf-8") as f:
        f.write("# YouTube Shorts Data\n\n")

        for v in sorted(videos, key=lambda x: x["video_number"]):

            number = f"{v['video_number']:04d}"

            f.write(f"# Short {number}\n\n")

            f.write(f"**Video ID:** {v.get('video_id', '')}  \n")
            f.write(f"**Title:** {v.get('title', '')}  \n")
            f.write(f"**URL:** {v.get('url', '')}  \n")

            f.write(
                f"**Publish Date:** "
                f"{v.get('publish_date') or 'UNAVAILABLE'}  \n"
            )

            f.write(
                f"**Publish Time:** "
                f"{v.get('publish_time') or 'UNAVAILABLE'}  \n"
            )

            f.write(
                f"**Duration:** "
                f"{v.get('duration_seconds') or 'UNAVAILABLE'} seconds  \n"
            )

            f.write("\n## Transcript\n\n")

            transcript = v.get(
                "transcript",
                "TRANSCRIPT UNAVAILABLE"
            )

            if not transcript:
                transcript = "TRANSCRIPT UNAVAILABLE"

            f.write(transcript.strip() + "\n\n")

            f.write("## Preview Grid\n\n")

            grid_paths = v.get("preview_grid_path", "")

            if grid_paths:
                for grid_path in grid_paths.split(";"):
                    grid_path = grid_path.strip()

                    if not grid_path:
                        continue

                    relative = os.path.relpath(
                        grid_path,
                        channel_dir
                    ).replace("\\", "/")

                    f.write(f"![Preview Grid]({relative})\n\n")
            else:
                f.write("UNAVAILABLE\n\n")

            f.write("---\n\n")

    return path

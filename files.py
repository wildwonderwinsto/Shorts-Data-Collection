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
    Generate shorts.csv — the master CSV with all columns including file paths.
    """
    path = os.path.join(channel_dir, "shorts.csv")
    fieldnames = [
        'video_number', 'video_id', 'title', 'url',
        'publish_datetime', 'publish_date', 'publish_time',
        'duration_seconds', 'transcript_available',
        'folder_path', 'transcript_path', 'preview_grid_path'
    ]
    with open(path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for v in videos:
            writer.writerow({
                'video_number': f"{v['video_number']:04d}",
                'video_id': v['video_id'],
                'title': v['title'],
                'url': v['url'],
                'publish_datetime': v.get('publish_datetime', ''),
                'publish_date': v.get('publish_date', ''),
                'publish_time': v.get('publish_time', ''),
                'duration_seconds': v.get('duration_seconds', ''),
                'transcript_available': v.get('transcript_available', False),
                'folder_path': v.get('folder_path', ''),
                'transcript_path': v.get('transcript_path', ''),
                'preview_grid_path': v.get('preview_grid_path', ''),
            })
    return path

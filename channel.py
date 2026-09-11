"""
Channel URL resolution and Shorts listing.
Resolves channel URLs, @handles, and channel IDs.
Lists all Shorts from a channel's /shorts tab using yt-dlp.
"""

import re
import sys
import yt_dlp

from config import MAX_SHORT_DURATION


def resolve_channel_url(channel_input):
    """
    Normalize any form of channel input into a /shorts tab URL.

    Accepts:
      - https://www.youtube.com/@handle
      - https://www.youtube.com/channel/UCxxxxx
      - https://www.youtube.com/c/ChannelName
      - @handle
      - UCxxxxx (raw channel ID)

    Returns: (shorts_url, channel_id_or_handle)
    """
    channel_input = channel_input.strip()

    # Already a full URL
    if channel_input.startswith(("http://", "https://")):
        # Strip trailing slashes and known tabs
        url = channel_input.rstrip('/')
        url = re.sub(r'/(shorts|videos|streams|playlists|community|featured|about)$', '', url)
        shorts_url = url + '/shorts'
        # Extract identifier for display
        match = re.search(r'youtube\.com/(@[\w.-]+|channel/(UC[\w-]+)|c/([\w.-]+))', url)
        if match:
            ident = match.group(1) or match.group(2) or match.group(3)
        else:
            ident = url.split('/')[-1]
        return shorts_url, ident

    # @handle format
    if channel_input.startswith('@'):
        shorts_url = f"https://www.youtube.com/{channel_input}/shorts"
        return shorts_url, channel_input

    # Raw channel ID (starts with UC)
    if channel_input.startswith('UC') and len(channel_input) >= 20:
        shorts_url = f"https://www.youtube.com/channel/{channel_input}/shorts"
        return shorts_url, channel_input

    # Assume it might be a handle without @
    shorts_url = f"https://www.youtube.com/@{channel_input}/shorts"
    return shorts_url, f"@{channel_input}"


def get_channel_info(shorts_url):
    """
    Fetch the channel name and ID from the shorts tab URL.
    Returns dict with channel_name, channel_id.
    """
    ydl_opts = {
        'extract_flat': True,
        'quiet': True,
        'no_warnings': True,
        'playlist_items': '1',  # only need one item to get channel info
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(shorts_url, download=False)
        channel_name = info.get('channel') or info.get('uploader') or info.get('title', 'Unknown')
        channel_id = info.get('channel_id') or info.get('uploader_id', '')

        # Clean up channel name
        if channel_name.endswith(' - Shorts'):
            channel_name = channel_name[:-len(' - Shorts')]

        return {
            'channel_name': channel_name,
            'channel_id': channel_id,
        }


def list_shorts(shorts_url, max_videos=None):
    """
    List all Shorts from a channel's /shorts tab.

    Returns a list of dicts sorted oldest -> newest:
    [
        {
            'video_id': 'abc123',
            'title': 'Short Title',
            'url': 'https://www.youtube.com/shorts/abc123',
            'duration': 42,
        },
        ...
    ]
    """
    ydl_opts = {
        'extract_flat': True,
        'quiet': True,
        'no_warnings': True,
    }

    print(f"\nFetching Shorts list from channel...")

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(shorts_url, download=False)

    entries = info.get('entries', [])
    if not entries:
        print("No Shorts found on this channel.")
        return []

    shorts = []
    for entry in entries:
        video_id = entry.get('id') or entry.get('url', '').split('/')[-1]
        if not video_id:
            continue

        duration = entry.get('duration')
        # Filter by duration if available — only include Shorts-length videos
        if duration is not None and duration > MAX_SHORT_DURATION:
            continue

        title = entry.get('title', 'Untitled')
        url = f"https://www.youtube.com/shorts/{video_id}"

        shorts.append({
            'video_id': video_id,
            'title': title,
            'url': url,
            'duration': duration,
        })

    # yt-dlp returns newest first from /shorts tab; reverse to get oldest first
    shorts.reverse()

    total = len(shorts)
    print(f"Found {total} Shorts on channel.")

    # Apply max_videos limit (take the most recent N after sorting oldest->newest)
    if max_videos and max_videos < total:
        # Keep the LAST max_videos entries (newest) so user gets the latest
        # But actually, user likely wants oldest-first processing. Let them decide via --start-date/--end-date.
        # With --max-videos, limit total count but keep oldest-first order.
        shorts = shorts[:max_videos]
        print(f"Limited to first {max_videos} Shorts (oldest first).")

    return shorts


def get_video_metadata(video_id):
    """
    Fetch detailed metadata for a single video using yt-dlp.

    Returns all raw date fields plus standard metadata.
    Never invents timestamps or converts relative dates.
    """
    url = f"https://www.youtube.com/shorts/{video_id}"

    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'skip_download': True,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)

    # Extract all available date/time fields — never fabricate
    timestamp = info.get('timestamp')            # Unix epoch of upload/publish
    upload_date = info.get('upload_date')         # YYYYMMDD string
    release_timestamp = info.get('release_timestamp')  # Unix epoch of scheduled release
    release_date = info.get('release_date')       # YYYYMMDD string

    # Determine the best publish date/time
    publish_datetime = None
    publish_date = None
    publish_time = None

    # Prefer release_timestamp (scheduled publish) over timestamp (upload)
    best_timestamp = release_timestamp or timestamp
    best_date_str = release_date or upload_date

    if best_timestamp is not None:
        from datetime import datetime, timezone
        dt = datetime.fromtimestamp(best_timestamp, tz=timezone.utc)
        publish_datetime = dt.strftime('%Y-%m-%d %I:%M %p UTC')
        publish_date = dt.strftime('%Y-%m-%d')
        publish_time = dt.strftime('%I:%M %p UTC')
    elif best_date_str:
        # Only a date available — no time
        try:
            publish_date = f"{best_date_str[:4]}-{best_date_str[4:6]}-{best_date_str[6:8]}"
            publish_datetime = publish_date
        except (IndexError, ValueError):
            publish_date = best_date_str

    duration = info.get('duration')

    metadata = {
        'video_id': video_id,
        'title': info.get('title', 'Untitled'),
        'url': url,
        'duration_seconds': duration,
        'channel_id': info.get('channel_id', ''),
        'channel_name': info.get('channel', '') or info.get('uploader', ''),

        # All raw date fields from yt-dlp — stored as-is
        'raw_timestamp': timestamp,
        'raw_upload_date': upload_date,
        'raw_release_timestamp': release_timestamp,
        'raw_release_date': release_date,

        # Derived (never invented)
        'publish_datetime': publish_datetime,
        'publish_date': publish_date,
        'publish_time': publish_time,
    }

    return metadata

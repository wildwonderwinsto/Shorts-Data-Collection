"""
Scan state persistence and resume logic.
Tracks completed video IDs, assigned numbers, failures, and per-output status.
Enables resuming interrupted scans and incremental updates.
Failed/incomplete Shorts are automatically retried on the next scan.
"""

import json
import os
from datetime import datetime, timezone


def get_state_path(channel_dir):
    """Return the path to scan_state.json for a channel."""
    return os.path.join(channel_dir, "scan_state.json")


def load_state(channel_dir):
    """
    Load existing scan state or return a fresh empty state.
    """
    path = get_state_path(channel_dir)
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return create_empty_state()


def create_empty_state():
    """Return a blank scan state dictionary."""
    return {
        "channel_id": None,
        "channel_name": None,
        "last_scan_timestamp": None,
        "total_shorts_found": 0,
        "completed_video_ids": [],
        "failed_video_ids": {},
        "next_video_number": 1,
        "videos": {},
    }


def save_state(channel_dir, state):
    """Persist the scan state to disk."""
    state["last_scan_timestamp"] = datetime.now(timezone.utc).isoformat()
    path = get_state_path(channel_dir)
    tmp_path = path + ".tmp"
    with open(tmp_path, 'w', encoding='utf-8') as f:
        json.dump(state, f, indent=2, ensure_ascii=False, default=str)
    os.replace(tmp_path, path)


def is_video_complete(state, video_id):
    """Check if a video has already been fully processed."""
    return video_id in state["completed_video_ids"]


def mark_video_complete(state, video_id, video_number, output_status=None):
    """
    Mark a video as successfully completed.

    Args:
        state: scan state dict
        video_id: YouTube video ID
        video_number: assigned sequential number
        output_status: optional dict with per-output status, e.g.
            {'metadata': 'complete', 'transcript': 'unavailable', 'grid': 'complete'}
    """
    if video_id not in state["completed_video_ids"]:
        state["completed_video_ids"].append(video_id)

    video_entry = {
        "video_number": video_number,
        "status": "complete",
    }
    if output_status:
        video_entry["output_status"] = output_status

    state["videos"][video_id] = video_entry

    if video_number >= state["next_video_number"]:
        state["next_video_number"] = video_number + 1

    # Remove from failed if it was there
    state["failed_video_ids"].pop(video_id, None)


def mark_video_failed(state, video_id, video_number, reason, output_status=None):
    """
    Record that a video failed processing.
    Preserves the video_number so it can be retried with the same number.
    Does NOT add to completed_video_ids so it will be retried on next scan.

    Args:
        state: scan state dict
        video_id: YouTube video ID
        video_number: assigned sequential number (preserved for retry)
        reason: string describing what failed
        output_status: optional dict with per-output status, e.g.
            {'metadata': 'complete', 'transcript': 'unavailable', 'grid': 'failed'}
    """
    state["failed_video_ids"][video_id] = reason

    video_entry = {
        "video_number": video_number,
        "status": "failed",
        "reason": reason,
    }
    if output_status:
        video_entry["output_status"] = output_status

    state["videos"][video_id] = video_entry

    # Advance the number counter so the number is reserved
    if video_number >= state["next_video_number"]:
        state["next_video_number"] = video_number + 1


def get_assigned_number(state, video_id):
    """
    Get the previously assigned number for a video, or None if not yet assigned.
    """
    video_info = state["videos"].get(video_id)
    if video_info:
        return video_info["video_number"]
    return None


def assign_number(state, video_id):
    """
    Assign the next available number to a video. Returns the number.
    If already assigned, returns the existing number.
    """
    existing = get_assigned_number(state, video_id)
    if existing is not None:
        return existing
    num = state["next_video_number"]
    state["videos"][video_id] = {
        "video_number": num,
        "status": "pending",
    }
    state["next_video_number"] = num + 1
    return num

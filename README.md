# YouTube Shorts Data Collector

A local Windows tool that collects metadata, transcripts, and high-resolution preview frame grids for every YouTube Short on a given channel.

**This is strictly a data collection and organization tool.** It does not analyze, score, rank, or recommend anything.

---

## Quick Start

### 1. Install

```
install.bat
```

This will:
- Check for Python 3.10+
- Create a virtual environment
- Install dependencies
- Check for FFmpeg (required for preview grids)

### 2. Run

**Interactive mode:**
```
run.bat
```

**Command line:**
```
run.bat "https://www.youtube.com/@ChannelName"
run.bat "@ChannelName" --max-videos 50
run.bat "UCxxxxx" --skip-transcripts
```

---

## Requirements

| Dependency | Required | Notes |
|---|---|---|
| Python 3.10+ | Yes | [python.org/downloads](https://www.python.org/downloads/) |
| FFmpeg | Yes (for grids) | `winget install ffmpeg` or [ffmpeg.org](https://ffmpeg.org/download.html) |

---

## What It Collects

For every Short on a channel:

| Data | File |
|---|---|
| Title, URL, Video ID, publish date/time, duration | `info.json` |
| Full transcript text | `transcript.txt` |
| High-resolution preview frame grid (1 frame/second) | `preview_grid.jpg` |

**Does NOT collect:** views, likes, comments, subscriber count, or any engagement/performance data.

---

## Command Line Options

```
python scan.py "CHANNEL_URL" [OPTIONS]

Options:
  --max-videos N        Maximum number of Shorts to process
  --start-date YYYY-MM-DD  Only include Shorts after this date
  --end-date YYYY-MM-DD    Only include Shorts before this date
  --skip-transcripts    Skip transcript collection
  --skip-grid           Skip preview grid generation
  --keep-videos         Keep downloaded video files
  --force               Reprocess all Shorts (ignore scan state)
  --output PATH         Output directory (default: ./YouTubeResearch)
```

### Input Formats

All of these work:
```
python scan.py "https://www.youtube.com/@ChannelName"
python scan.py "https://www.youtube.com/channel/UCxxxxx"
python scan.py "@ChannelName"
python scan.py "UCxxxxx"
```

---

## Output Structure

```
YouTubeResearch/
└── ChannelName/
    ├── shorts.csv              Master CSV with all data
    ├── titles.txt              Simple title list
    ├── titles.csv              Titles with metadata
    ├── scan_state.json         Resume/incremental scan state
    │
    └── shorts/
        ├── 0001_VIDEO_ID_Title/
        │   ├── 0001_VIDEO_ID_info.json
        │   ├── 0001_VIDEO_ID_transcript.txt
        │   └── 0001_VIDEO_ID_preview_grid.jpg
        │
        ├── 0002_VIDEO_ID_Title/
        │   ├── 0002_VIDEO_ID_info.json
        │   ├── 0002_VIDEO_ID_transcript.txt
        │   └── 0002_VIDEO_ID_preview_grid_part01.jpg
        │   └── 0002_VIDEO_ID_preview_grid_part02.jpg
        │
        └── ...
```

### Numbering

- `0001` = oldest Short on the channel
- Numbers increase chronologically toward newest
- Numbers are permanent and never change on re-scan

### Preview Grids

- Extracted at **1 frame per second** using FFmpeg
- Native resolution (1080×1920 when available)
- 5-column layout with timestamps below each frame
- Automatically split into parts when frame count exceeds 30

### Transcripts

Priority order:
1. YouTube manual captions (any language)
2. YouTube auto-generated captions (any language)
3. `TRANSCRIPT UNAVAILABLE`

---

## Resume & Incremental Updates

- **Interrupted scan:** Run the same command again — it continues where it stopped.
- **New Shorts:** Re-scanning a channel only processes newly discovered Shorts.
- **Force reprocess:** Use `--force` to reprocess everything.



---

## CSV Columns

### shorts.csv (Master)
```
video_number, video_id, title, url, publish_datetime, publish_date,
publish_time, duration_seconds, transcript_available, folder_path,
transcript_path, preview_grid_path
```

### titles.csv
```
video_number, video_id, title, publish_datetime, publish_date,
publish_time, duration_seconds, url
```

---

## Troubleshooting

| Issue | Solution |
|---|---|
| `FFmpeg not found` | Install FFmpeg and add to PATH, then restart terminal |
| `No Shorts found` | Check the channel URL is correct and has Shorts |
| YouTube rate limiting | Use `--max-videos` to process in smaller batches |
| Scan interrupted | Just run the same command again — it resumes |
| Want to redo everything | Use `--force` flag |

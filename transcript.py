"""
Transcript fetching with multi-language support and fallback chain.

Priority order:
  1. YouTube captions via youtube-transcript-api (manual captions, any language)
  2. YouTube captions via youtube-transcript-api (auto-generated, any language)
  3. TRANSCRIPT UNAVAILABLE

Never fabricates transcript content.
"""

import os
import sys
import traceback


def fetch_youtube_transcript(video_id):
    """
    Try to get transcript from YouTube captions.

    Inspects the available transcript list:
      - Prefers manually created transcripts (any language)
      - Falls back to auto-generated transcripts (any language)

    Returns transcript text or None if unavailable.
    """
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
    except ImportError:
        print("    [!] youtube-transcript-api not installed, skipping YouTube captions.")
        return None

    try:
        # Fetch the list of available transcripts
        ytt_api = YouTubeTranscriptApi()
        transcript_list = ytt_api.list(video_id)

        transcript = None

        # First: try manually created transcripts (any language)
        try:
            manual_transcripts = list(transcript_list._manually_created_transcripts.values())
            if manual_transcripts:
                transcript = manual_transcripts[0]  # Use first available manual transcript
        except (AttributeError, StopIteration):
            pass

        # Second: try auto-generated transcripts (any language)
        if transcript is None:
            try:
                auto_transcripts = list(transcript_list._generated_transcripts.values())
                if auto_transcripts:
                    transcript = auto_transcripts[0]  # Use first available auto transcript
            except (AttributeError, StopIteration):
                pass

        # Fallback: try finding any transcript at all
        if transcript is None:
            try:
                transcript = transcript_list.find_transcript(
                    # Try common languages first, but the API will return whatever's available
                    ['en', 'es', 'fr', 'de', 'pt', 'ja', 'ko', 'zh', 'hi', 'ar', 'ru']
                )
            except Exception:
                pass

        if transcript is None:
            return None

        # Fetch the actual transcript data
        fetched = transcript.fetch()
        # Join all text segments into a single transcript
        text_parts = []
        for segment in fetched:
            text = segment.get('text', '') if isinstance(segment, dict) else getattr(segment, 'text', str(segment))
            text_parts.append(text)

        full_text = ' '.join(text_parts).strip()
        return full_text if full_text else None

    except Exception as e:
        print(f"    [!] YouTube transcript fetch failed: {e}")
        return None


def get_transcript(video_id):
    """
    Main transcript fetching function.

    Tries in order:
      1. YouTube captions (manual, any language)
      2. YouTube captions (auto-generated, any language)
      3. Returns "TRANSCRIPT UNAVAILABLE"

    Returns: (transcript_text, is_available)
      - transcript_text: the transcript string
      - is_available: True if a real transcript was obtained
    """
    # Step 1+2: Try YouTube transcript API
    print("    Fetching transcript from YouTube captions...")
    transcript = fetch_youtube_transcript(video_id)
    if transcript:
        print("    Transcript obtained from YouTube captions.")
        return transcript, True

    # Step 3: No transcript available
    print("    [!] No transcript available for this Short.")
    return "TRANSCRIPT UNAVAILABLE", False

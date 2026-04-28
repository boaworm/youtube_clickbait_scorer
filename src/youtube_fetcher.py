"""Fetch YouTube video data: metadata and transcript with fallback strategies."""

import os
import time
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Optional

from .metadata_extractor import extract_video_id, get_video_info as get_info_ytdlp
from .video_downloader import download_audio
from .audio_extractor import convert_audio
from .transcriber import transcribe


def _ts():
    return datetime.now().strftime("[%H:%M:%S]")


def get_cache_dir(video_id: str) -> Path:
    """Get cache directory path for a video ID."""
    cache_base = Path(__file__).parent.parent / "tmp" / "audio_cache"
    cache_base.mkdir(parents=True, exist_ok=True)
    return cache_base / video_id


def clean_old_cache(max_entries: int = 10):
    """
    Clean old cache entries, keeping only the most recent ones.

    Args:
        max_entries: Maximum number of cache directories to keep
    """
    cache_base = Path(__file__).parent.parent / "tmp" / "audio_cache"
    if not cache_base.exists():
        return

    # Get all cache directories sorted by modification time (newest first)
    cache_dirs = sorted(
        [d for d in cache_base.iterdir() if d.is_dir()],
        key=lambda d: d.stat().st_mtime,
        reverse=True
    )

    # Delete old entries beyond max_entries
    for old_dir in cache_dirs[max_entries:]:
        try:
            import shutil
            shutil.rmtree(old_dir)
            print(f"{_ts()} INFO: Cleaned old cache: {old_dir.name}")
        except Exception as e:
            print(f"{_ts()} INFO: Failed to clean cache {old_dir.name}: {e}")


def fetch_video_metadata(video_id: str) -> dict:
    """Fetch video metadata via yt-dlp."""
    try:
        info = get_info_ytdlp(f"https://www.youtube.com/watch?v={video_id}")
        live_status = info.get("live_status", "")
        is_live = (
            live_status == "is_live" or
            info.get("is_live", False) or
            info.get("is_upcoming", False)
        )
        return {
            "title": info.get("title", ""),
            "description": info.get("description", ""),
            "channel_title": info.get("channel", ""),
            "published_at": info.get("publish_date", ""),
            "is_live": is_live,
        }
    except Exception:
        return {
            "title": f"Video {video_id}",
            "description": "",
            "channel_title": "Unknown",
            "published_at": "",
            "is_live": False,
        }


def fetch_transcript(video_id: str, verbose: bool = False) -> Optional[str]:
    """
    Fetch transcript by downloading audio and transcribing with MLX Whisper.
    Results are cached to avoid re-downloading.
    """
    video_url = f"https://www.youtube.com/watch?v={video_id}"
    cache_dir = get_cache_dir(video_id)
    transcript_file = cache_dir / "transcript.txt"
    audio_file = cache_dir / "audio.m4a"
    wav_file = cache_dir / "audio.wav"

    if transcript_file.exists():
        if verbose:
            print(f"{_ts()} INFO: [{video_url}] Using cached transcript")
        return transcript_file.read_text()

    try:
        cache_dir.mkdir(parents=True, exist_ok=True)

        if audio_file.exists():
            if verbose:
                print(f"{_ts()} INFO: [{video_url}] Using cached audio file")
        else:
            print(f"{_ts()} INFO: [{video_url}] Downloading audio")
            _t = time.monotonic()
            audio_file = download_audio(video_url, cache_dir, output_format="m4a")
            print(f"{_ts()} INFO: [{video_url}] Downloading audio [DONE in {round(time.monotonic() - _t)} sec]")

        if not wav_file.exists():
            if verbose:
                print(f"{_ts()} INFO: [{video_url}] Converting to WAV for Whisper...")
            convert_audio(audio_file, wav_file)

        print(f"{_ts()} INFO: [{video_url}] Transcribing audio")
        _t = time.monotonic()
        transcript = transcribe(wav_file, model="mlx-community/whisper-large-v3-turbo")
        print(f"{_ts()} INFO: [{video_url}] Transcribing audio [DONE in {round(time.monotonic() - _t)} sec]")
        transcript_file.write_text(transcript)

        if verbose:
            print(f"{_ts()} INFO: [{video_url}] Transcription complete (cached)")

        return transcript

    except Exception as e:
        if verbose:
            print(f"{_ts()} INFO: [{video_url}] Transcription failed: {type(e).__name__}")
        return None


def fetch_video_data(url: str, verbose: bool = False) -> dict:
    """
    Fetch all available video data from a YouTube URL.

    Uses progressive fallback strategy:
    - Metadata: Always uses yt-dlp (no API key required)
    - Transcript: Cache → API → Download + MLX Whisper (all cached)

    Args:
        url: YouTube video URL
        verbose: Print progress information

    Returns:
        Dict with keys: video_id, title, description, transcript,
                       channel_title, published_at, source
    """
    video_id = extract_video_id(url)

    if verbose:
        print(f"{_ts()} INFO: [{url}] Extracted video ID: {video_id}")

    # Fetch metadata (yt-dlp, no API required)
    if verbose:
        print(f"{_ts()} INFO: [{url}] Fetching metadata...")
    metadata = fetch_video_metadata(video_id)

    # Fetch transcript with fallback
    if verbose:
        print(f"{_ts()} INFO: [{url}] Fetching transcript...")
    transcript = fetch_transcript(video_id, verbose=verbose)

    return {
        "video_id": video_id,
        "title": metadata.get("title", ""),
        "description": metadata.get("description", ""),
        "transcript": transcript,
        "channel_title": metadata.get("channel_title", ""),
        "published_at": metadata.get("published_at", ""),
        "source": "cache" if transcript and Path(get_cache_dir(video_id) / "transcript.txt").exists() else "api",
    }

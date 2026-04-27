"""Fetch YouTube video data: metadata and transcript with fallback strategies."""

import os
import hashlib
from pathlib import Path
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from youtube_transcript_api import YouTubeTranscriptApi
from typing import Optional

from .metadata_extractor import extract_video_id, get_video_info as get_info_ytdlp
from .video_downloader import download_audio
from .audio_extractor import convert_audio
from .transcriber import transcribe
from .cleanup import TempFileManager
from .exceptions import FallbackExhaustedError


def get_cache_dir(video_id: str) -> Path:
    """Get cache directory path for a video ID."""
    cache_base = Path(__file__).parent.parent / "tmp" / "audio_cache"
    cache_base.mkdir(parents=True, exist_ok=True)
    return cache_base / video_id


def fetch_video_metadata(video_id: str) -> dict:
    """
    Fetch video metadata using yt-dlp (no API key required).

    Falls back to YouTube Data API if API key is available.

    Args:
        video_id: YouTube video ID

    Returns:
        Dict with keys: title, description, channel_title, published_at
    """
    # Prefer yt-dlp extraction (always works without API key)
    try:
        info = get_info_ytdlp(f"https://www.youtube.com/watch?v={video_id}")
        return {
            "title": info.get("title", ""),
            "description": info.get("description", ""),
            "channel_title": info.get("channel", ""),
            "published_at": info.get("publish_date", ""),
        }
    except Exception as e:
        # Fallback to YouTube Data API if available
        api_key = os.getenv("YOUTUBE_API_KEY")
        if api_key:
            try:
                youtube = build("youtube", "v3", developerKey=api_key)
                response = youtube.videos().list(
                    part="snippet",
                    id=video_id
                ).execute()

                if response["items"]:
                    snippet = response["items"][0]["snippet"]
                    return {
                        "title": snippet.get("title", ""),
                        "description": snippet.get("description", ""),
                        "channel_title": snippet.get("channelTitle", ""),
                        "published_at": snippet.get("publishedAt", ""),
                    }
            except HttpError:
                pass

        # If all else fails, return minimal metadata
        return {
            "title": f"Video {video_id}",
            "description": "",
            "channel_title": "Unknown",
            "published_at": "",
        }


def fetch_transcript(video_id: str, languages: list[str] = None, verbose: bool = False) -> Optional[str]:
    """
    Fetch transcript with fallback to local transcription.

    Strategy:
    1. Check audio cache for existing transcript
    2. Try youtube-transcript-api
    3. Fallback: Download audio + transcribe with MLX Whisper (cached)

    Args:
        video_id: YouTube video ID
        languages: Preferred languages for transcript
        verbose: Print progress information

    Returns:
        Transcript text, or None if unavailable
    """
    if languages is None:
        languages = ["en", "en-US"]

    cache_dir = get_cache_dir(video_id)
    transcript_file = cache_dir / "transcript.txt"
    audio_file = cache_dir / "audio.m4a"
    wav_file = cache_dir / "audio.wav"

    # Check cache first
    if transcript_file.exists():
        if verbose:
            print("  ✓ Using cached transcript")
        return transcript_file.read_text()

    # Try transcript API first
    try:
        if verbose:
            print("  Attempting to fetch transcript from API...")
        transcript_list = YouTubeTranscriptApi.fetch(video_id, languages=languages)
        transcript_text = " ".join([entry["text"] for entry in transcript_list])
        if verbose:
            print("  ✓ Transcript fetched from API")
        # Cache the result
        cache_dir.mkdir(parents=True, exist_ok=True)
        transcript_file.write_text(transcript_text)
        return transcript_text
    except Exception as e:
        if verbose:
            print(f"  Transcript API failed: {type(e).__name__}: {e}")
            print("  Falling back to local transcription...")

        # Fallback: download and transcribe
        try:
            video_url = f"https://www.youtube.com/watch?v={video_id}"

            cache_dir.mkdir(parents=True, exist_ok=True)

            # Download audio (cached)
            if audio_file.exists():
                if verbose:
                    print("  Using cached audio file")
            else:
                if verbose:
                    print("  Downloading audio (m4a)...")
                audio_file = download_audio(video_url, cache_dir, output_format="m4a")

            # Convert to WAV (cached)
            if not wav_file.exists():
                if verbose:
                    print("  Converting to WAV for Whisper...")
                convert_audio(audio_file, wav_file)

            # Transcribe (MLX Whisper)
            if verbose:
                print("  Transcribing with MLX Whisper...")
            transcript = transcribe(wav_file, model="mlx-community/whisper-large-v3-turbo")

            # Cache the transcript
            transcript_file.write_text(transcript)

            if verbose:
                print("  ✓ Transcription complete (cached)")

            return transcript

        except Exception as fallback_error:
            if verbose:
                print(f"  Local transcription also failed: {type(fallback_error).__name__}")
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
        print(f"  Extracted video ID: {video_id}")

    # Fetch metadata (yt-dlp, no API required)
    if verbose:
        print("Fetching metadata...")
    metadata = fetch_video_metadata(video_id)

    # Fetch transcript with fallback
    if verbose:
        print("Fetching transcript...")
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

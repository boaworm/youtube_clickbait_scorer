"""Extract video metadata from YouTube page HTML using yt-dlp."""

import yt_dlp
from typing import Optional


def extract_video_id(url: str) -> str:
    """
    Extract video ID from a YouTube URL.

    Supports:
    - https://www.youtube.com/watch?v=VIDEO_ID
    - https://youtu.be/VIDEO_ID

    Returns:
        Video ID string

    Raises:
        ValueError: If URL format is invalid
    """
    if "youtube.com/watch?v=" in url:
        return url.split("v=")[1].split("&")[0]
    elif "youtu.be/" in url:
        return url.split("youtu.be/")[1].split("?")[0]
    else:
        raise ValueError(f"Invalid YouTube URL: {url}")


def get_video_info(video_url: str) -> dict:
    """
    Extract video metadata using yt-dlp (no API key needed).

    Args:
        video_url: YouTube video URL

    Returns:
        Dict with keys: title, description, uploader, duration, id
    """
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': False,
        'noplaylist': True,
        'skip_download': True,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(video_url, download=False)
        # Check live status - yt-dlp uses multiple fields
        live_status = info.get("live_status", "")
        is_live = (
            live_status == "is_live" or
            info.get("is_live", False) or
            info.get("is_upcoming", False)
        )

        return {
            "title": info.get("title", ""),
            "description": info.get("description", "") or "",
            "channel": info.get("uploader", "") or info.get("channel", ""),
            "duration": info.get("duration", 0),
            "view_count": info.get("view_count", 0),
            "publish_date": info.get("upload_date", ""),
            "is_live": is_live,
        }


def fetch_video_metadata(video_id: str) -> dict:
    """
    Extract video metadata by parsing YouTube page HTML via yt-dlp.

    Args:
        video_id: YouTube video ID

    Returns:
        Dict with keys: title, description, channel, duration, view_count, publish_date
    """
    video_url = f"https://www.youtube.com/watch?v={video_id}"
    return get_video_info(video_url)

"""Download audio from YouTube using yt-dlp."""

import yt_dlp
from pathlib import Path
from typing import Optional

from .exceptions import DownloadError


def download_audio(
    video_url: str,
    output_dir: Path,
    output_format: str = "m4a",
    timeout: int = 300
) -> Optional[Path]:
    """
    Download audio-only from YouTube using yt-dlp.

    Downloads the best available audio stream and converts to specified format.

    Args:
        video_url: YouTube video URL
        output_dir: Directory to save downloaded file
        output_format: Output audio format (m4a, mp3, wav)
        timeout: Maximum download time in seconds

    Returns:
        Path to downloaded audio file

    Raises:
        DownloadError: If download fails
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    # Use safe filename template to avoid Unicode character issues
    output_template = str(output_dir / "%(title)s.%(ext)s")

    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': output_template,
        'quiet': True,
        'no_warnings': True,
        'progress_hooks': [],
        'timeout': timeout,
        'restrictfilenames': True,  # Use safe filenames (no Unicode chars)
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': output_format,
            'preferredquality': '192',
        }],
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=True)

            # Scan directory for the actual downloaded file
            # (yt-dlp may modify the filename during processing)
            for f in output_dir.iterdir():
                if f.suffix == f'.{output_format}':
                    return f

            # Fallback: construct expected path
            return output_dir / f"{info.get('title', 'audio')}.{output_format}"

    except Exception as e:
        raise DownloadError(video_url, str(e))


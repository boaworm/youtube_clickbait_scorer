"""Audio format conversion using ffmpeg."""

import subprocess
from pathlib import Path
from typing import Optional

from .exceptions import ExtractionError


def convert_audio(
    input_path: Path,
    output_path: Path,
    format: str = "wav",
    sample_rate: int = 16000
) -> Optional[Path]:
    """
    Convert audio file to different format/sample rate.

    Args:
        input_path: Path to input audio file
        output_path: Path for output file
        format: Output format (whisper prefers wav)
        sample_rate: Output sample rate (Whisper uses 16kHz)

    Returns:
        Path to converted file, or None if failed
    """
    cmd = [
        "ffmpeg", "-i", str(input_path),
        "-ar", str(sample_rate),
        "-ac", "1",  # Mono
        "-y",
        str(output_path),
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300
        )
        if result.returncode != 0:
            raise ExtractionError(str(input_path), result.stderr)
        return output_path
    except subprocess.TimeoutExpired:
        raise ExtractionError(str(input_path), "Audio conversion timed out")
    except Exception as e:
        raise ExtractionError(str(input_path), str(e))

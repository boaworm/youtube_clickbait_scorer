"""Transcribe audio files using MLX Whisper (Apple Silicon optimized)."""

import os
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

# Load environment variables for HF token
load_dotenv()

os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")

import mlx_whisper


def transcribe(
    audio_path: Path,
    model: str = "mlx-community/whisper-large-v3-turbo",
    language: Optional[str] = None
) -> str:
    """
    Generate transcript from audio file using MLX Whisper.

    Uses Apple Neural Engine (ANE) for fast transcription on M1/M2/M3 chips.

    Args:
        audio_path: Path to audio file (WAV preferred)
        model: MLX Whisper model path (default: mlx-community/whisper-large-v3-turbo)
        language: ISO 639-1 language code (auto-detected if None)

    Returns:
        Transcribed text

    Raises:
        TranscriptionError: If transcription fails
    """
    try:
        options = {}
        if language:
            options["language"] = language

        result = mlx_whisper.transcribe(
            str(audio_path),
            path_or_hf_repo=model,
            **options
        )
        return result["text"]

    except Exception as e:
        from .exceptions import TranscriptionError
        raise TranscriptionError(str(audio_path), str(e))

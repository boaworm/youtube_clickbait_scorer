"""Detect AI-generated narration in audio using a wav2vec2 deepfake classifier.

Runs on Apple Silicon GPU via MPS when available. Model weights and any other
HuggingFace artifacts are cached under the project-local ./huggingface/ directory
so nothing is written to ~/.cache/huggingface.
"""

import os
import json
import subprocess
from pathlib import Path
from typing import Optional
from datetime import datetime

_PROJECT_ROOT = Path(__file__).parent.parent
_HF_CACHE = _PROJECT_ROOT / "huggingface"
_HF_CACHE.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("HF_HOME", str(_HF_CACHE))
os.environ.setdefault("HUGGINGFACE_HUB_CACHE", str(_HF_CACHE / "hub"))
os.environ.setdefault("TRANSFORMERS_CACHE", str(_HF_CACHE / "hub"))

import torch

_MODEL_NAME = os.getenv("VOICE_DETECTOR_MODEL", "MelodyMachine/Deepfake-audio-detection")
_SAMPLE_SECONDS = int(os.getenv("VOICE_SAMPLE_SECONDS", "60"))
_CHUNK_SECONDS = int(os.getenv("VOICE_CHUNK_SECONDS", "5"))
# A chunk is considered AI when its 'fake' probability is above this.
_CHUNK_AI_THRESHOLD = float(os.getenv("VOICE_CHUNK_AI_THRESHOLD", "0.7"))
# The whole clip is considered AI when at least this fraction of chunks are AI.
_OVERALL_AI_FRACTION = float(os.getenv("VOICE_OVERALL_AI_FRACTION", "0.5"))

_pipeline = None


def _ts() -> str:
    return datetime.now().strftime("[%H:%M:%S]")


def _get_device() -> str:
    if torch.backends.mps.is_available():
        return "mps"
    if torch.cuda.is_available():
        return "cuda"
    return "cpu"


def _load_pipeline():
    global _pipeline
    if _pipeline is not None:
        return _pipeline
    from transformers import pipeline
    device = _get_device()
    print(f"{_ts()} INFO: Loading voice detector '{_MODEL_NAME}' on {device}")
    _pipeline = pipeline(
        "audio-classification",
        model=_MODEL_NAME,
        device=device,
    )
    return _pipeline


def _slice_chunks(input_wav: Path, out_dir: Path, total_seconds: int, chunk_seconds: int) -> list[Path]:
    """Split the first `total_seconds` of `input_wav` into mono 16kHz chunks of `chunk_seconds`."""
    out_dir.mkdir(parents=True, exist_ok=True)
    pattern = str(out_dir / "chunk_%03d.wav")
    result = subprocess.run(
        [
            "ffmpeg", "-y", "-i", str(input_wav),
            "-t", str(total_seconds),
            "-ar", "16000", "-ac", "1",
            "-f", "segment",
            "-segment_time", str(chunk_seconds),
            "-reset_timestamps", "1",
            pattern,
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg chunking failed: {result.stderr}")
    return sorted(out_dir.glob("chunk_*.wav"))


def _extract_ai_score(raw: list[dict]) -> float:
    """Pull the AI/fake probability out of a pipeline result (list of {label, score})."""
    scores = {item["label"].lower(): float(item["score"]) for item in raw}
    for k in ("fake", "spoof", "ai", "synthetic", "deepfake"):
        if k in scores:
            return scores[k]
    for k in ("real", "bonafide", "human", "genuine"):
        if k in scores:
            return 1.0 - scores[k]
    return 0.0


def analyze_voice(wav_path: Path, cache_dir: Optional[Path] = None) -> dict:
    """
    Score whether the narration in `wav_path` is AI-generated.

    Slices the first VOICE_SAMPLE_SECONDS into VOICE_CHUNK_SECONDS windows, scores
    each independently (matching the short-clip distribution these models were trained
    on), then aggregates: ai_probability is the fraction of chunks whose fake score
    exceeded VOICE_CHUNK_AI_THRESHOLD.
    """
    if cache_dir is not None:
        cache_file = cache_dir / "voice_authenticity.json"
        if cache_file.exists():
            try:
                return json.loads(cache_file.read_text())
            except Exception:
                pass

    chunks_dir = (cache_dir or wav_path.parent) / "voice_chunks"
    if chunks_dir.exists():
        for f in chunks_dir.glob("chunk_*.wav"):
            f.unlink()
    chunks = _slice_chunks(wav_path, chunks_dir, _SAMPLE_SECONDS, _CHUNK_SECONDS)
    if not chunks:
        raise RuntimeError("No audio chunks produced")

    pipe = _load_pipeline()
    raw_results = pipe([str(c) for c in chunks], batch_size=8)

    per_chunk = []
    for chunk_path, raw in zip(chunks, raw_results):
        ai = _extract_ai_score(raw)
        per_chunk.append({
            "start_sec": int(chunk_path.stem.split("_")[-1]) * _CHUNK_SECONDS,
            "ai_score": round(ai, 4),
            "is_ai": ai >= _CHUNK_AI_THRESHOLD,
        })

    ai_chunks = sum(1 for c in per_chunk if c["is_ai"])
    ai_fraction = ai_chunks / len(per_chunk)
    mean_ai = sum(c["ai_score"] for c in per_chunk) / len(per_chunk)

    result = {
        "model": _MODEL_NAME,
        "device": _get_device(),
        "sample_seconds": _SAMPLE_SECONDS,
        "chunk_seconds": _CHUNK_SECONDS,
        "num_chunks": len(per_chunk),
        "ai_chunks": ai_chunks,
        "ai_probability": round(ai_fraction, 4),
        "real_probability": round(1.0 - ai_fraction, 4),
        "mean_ai_score": round(mean_ai, 4),
        "is_ai": ai_fraction >= _OVERALL_AI_FRACTION,
        "chunk_ai_threshold": _CHUNK_AI_THRESHOLD,
        "overall_ai_fraction_threshold": _OVERALL_AI_FRACTION,
        "per_chunk": per_chunk,
    }

    if cache_dir is not None:
        try:
            (cache_dir / "voice_authenticity.json").write_text(json.dumps(result, indent=2))
        except Exception:
            pass
        for f in chunks_dir.glob("chunk_*.wav"):
            try:
                f.unlink()
            except Exception:
                pass
        try:
            chunks_dir.rmdir()
        except Exception:
            pass

    return result


def load_cached(cache_dir: Path) -> Optional[dict]:
    """Return the cached voice_authenticity result for a video, if present."""
    f = cache_dir / "voice_authenticity.json"
    if not f.exists():
        return None
    try:
        return json.loads(f.read_text())
    except Exception:
        return None

# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

YouTube Clickbait Detector - Analyzes YouTube videos to determine if titles make claims not substantiated by the actual content (e.g., "Leak confirmed" when the video only contains speculation).

## Setup

```bash
# Create and activate virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Install system dependencies (if not already installed)
brew install yt-dlp ffmpeg

# Configure environment variables
cp .env.example .env
# Edit .env and add:
#   ANTHROPIC_BASE_URL - LLM endpoint
#   ANTHROPIC_MODEL - Model name
#   ANTHROPIC_AUTH_TOKEN - Auth token
#
# YOUTUBE_API_KEY is optional - not required for functionality
```

## Usage

```bash
# Analyze a video
python -m src.main "https://www.youtube.com/watch?v=VIDEO_ID"

# Verbose output (shows download/transcription progress)
python -m src.main -v "https://www.youtube.com/watch?v=VIDEO_ID"
```

## Architecture

```
src/
  youtube_fetcher.py      - Main fetcher with progressive fallback strategy
  metadata_extractor.py   - Extracts metadata via yt-dlp (no API needed)
  video_downloader.py     - Downloads audio-only via yt-dlp
  audio_extractor.py      - Converts audio formats via ffmpeg
  transcriber.py          - Whisper-based transcription
  clickbait_analyzer.py   - LLM-based clickbait analysis
  cleanup.py              - Temp file management
  exceptions.py           - Custom exceptions
  main.py                 - CLI entry point
```

### Data Flow

```
URL → extract video ID
    → metadata_extractor (yt-dlp, no API key required)
    → transcript fetch:
        1. Try youtube-transcript-api
        2. Fallback: download audio → convert → Whisper transcribe
    → clickbait_analyzer (LLM comparison)
    → structured verdict
```

### Fallback Strategy

| Component | Primary | Fallback |
|-----------|---------|----------|
| Metadata | yt-dlp HTML extraction | N/A (always works) |
| Transcript | youtube-transcript-api | Download audio + Whisper |

The analyzer looks for mismatches between definitive claims in titles ("confirmed", "breaking") and speculative/vague content in the transcript.

## Guidelines

- Always use the virtual environment (`ytv-env/` or `venv/`)
- Use `tmp/` for any temporary files (cache, downloads, etc.)
- Never write files outside the project directory
- Audio-only downloads (not full video) for transcription efficiency
- Temp files are automatically cleaned up after processing
- **NEVER pipe to `head`, `tail`, `grep` or similar** - these hide hanging processes. Use `tee tmp/some_file` instead for long-running commands.

# YouTube Clickbait Detector

Analyzes YouTube videos to determine if titles make claims not substantiated
by the actual content (e.g., "Leak confirmed" when the video only contains
speculation).

## Quick Start

```bash
# Create and activate virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Analyze a video
python -m src.main "https://www.youtube.com/watch?v=VIDEO_ID"

# Verbose output (shows full description and transcript)
python -m src.main -v "https://www.youtube.com/watch?v=VIDEO_ID"
```

## System Requirements

- **Python**: 3.14+
- **yt-dlp**: Installed via Homebrew (`brew install yt-dlp`)
- **ffmpeg**: Installed via Homebrew (`brew install ffmpeg`)

## Output Format

```
Title: MacBook M6 ULTRA Just Got CONFIRMED - 8 LEAKS Explained!
-----------------------------------
Initial score: 95% clickbait

Transcription score: 95% clickbait

-----------------------------------
Analysis: CLICKBAIT (95%)

The title explicitly states 'MacBook M6 ULTRA Just Got CONFIRMED,' implying
definitive verification of the product's existence and specifications, yet
the video content is entirely speculative. Throughout the transcript, the
presenter repeatedly uses qualifiers such as 'could be releasing,' 'leaks
and rumors,' 'could potentially still be on the cards,' and 'potentially we
could have the m6 ultra chip,' with no actual confirmation from Apple or
definitive sources provided. This discrepancy between the definitive claim
in the title and the uncertain, rumor-based nature of the content fits the
strict definition of clickbait where a title promises confirmation but the
video only speculates.
```

## How It Works

### 1. Metadata Extraction (No API Key Required)

Uses `yt-dlp` to extract video metadata directly from the YouTube page HTML:
- Title
- Description
- Channel name
- Publish date

**No YouTube Data API key needed** - works entirely through web scraping.

### 2. Transcript Fetching (Progressive Fallback)

The system tries multiple methods to get a transcript:

| Method | Description |
|--------|-------------|
| **youtube-transcript-api** | First attempt - fetches available captions |
| **MLX Whisper** | Fallback: downloads audio, transcribes locally using
MLX-optimized Whisper |

### 3. Audio Processing (Fallback Only)

When captions aren't available:

1. **Download**: `yt-dlp` downloads audio-only stream (m4a format)
2. **Convert**: `ffmpeg` converts to WAV (16kHz mono for Whisper)
3. **Transcribe**: MLX Whisper
   (`mlx-community/whisper-large-v3-turbo`) generates the transcript using
   Apple's Neural Engine
4. **Cache**: Results are cached for future runs

### 4. Clickbait Analysis

The LLM compares:
- **Title claims**: Definitive language ("confirmed", "breaking", "leak")
- **Actual content**: What the transcript actually says

Key indicators of clickbait:
- Title makes definitive claims but content is speculative
- "Confirmed" in title but only rumors in video
- "Breaking news" for unverified information
- Sensational language not supported by content

The analysis returns:
- **Initial score**: Based on title and description alone
- **Transcription score**: Based on full transcript analysis
- **Reasoning**: A paragraph explaining the verdict with specific examples

## Project Structure

```
youtube-verifier/
├── src/
│   ├── __init__.py
│   ├── main.py              # CLI entry point
│   ├── youtube_fetcher.py   # Main fetcher with fallback logic
│   ├── metadata_extractor.py # yt-dlp metadata extraction
│   ├── video_downloader.py  # Audio download via yt-dlp
│   ├── audio_extractor.py   # ffmpeg audio conversion
│   ├── transcriber.py       # MLX Whisper transcription
│   ├── clickbait_analyzer.py # LLM-based analysis
│   ├── cleanup.py           # Temp file management
│   └── exceptions.py        # Custom exceptions
├── tmp/                     # Temporary files (auto-cleaned)
├── requirements.txt
└── README.md
```

## Environment Variables

Optional configuration via `.env` file:

```bash
# YouTube Data API (optional - not required for basic functionality)
YOUTUBE_API_KEY=your_api_key_here

# LLM configuration (for clickbait analysis)
# If using a local llama.cpp server:
ANTHROPIC_BASE_URL=http://localhost:8080
ANTHROPIC_MODEL=model-name
ANTHROPIC_AUTH_TOKEN=token

# Or if using Anthropic Cloud API directly:
ANTHROPIC_API_KEY=sk-ant-...

# Hugging Face token (optional - for MLX Whisper model downloads)
# Get one at: https://huggingface.co/settings/tokens
HF_TOKEN=
```

### LLM Tuning

The clickbait analysis uses an LLM to evaluate title vs content alignment. Default
parameters are tuned for Qwen 3.5 via llama.cpp. If you're using a different model
or getting inconsistent results, you may need to adjust:

- **Temperature**: Lower (0.1-0.3) for more consistent scores
- **Model choice**: Larger models typically produce better reasoning
- **Prompt**: The system prompt in `src/clickbait_analyzer.py` can be customized

## Troubleshooting

### "Numpy is not available" error
```bash
pip install "numpy<2"
```

### Audio download fails
- Ensure `yt-dlp` is installed: `brew install yt-dlp`
- Check network connectivity

### Transcription fails
- Ensure `ffmpeg` is installed: `brew install ffmpeg`
- Try a different video (some have protected audio)

### Hugging Face authentication errors
- Add your Hugging Face token to `.env`: `HF_TOKEN=hf_xxxxx`
- Get a free token at: https://huggingface.co/settings/tokens

## License

MIT

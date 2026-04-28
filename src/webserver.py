"""Simple web UI for YouTube clickbait analysis."""

import os
import sys
import time
import asyncio
import json
from datetime import datetime
from pathlib import Path

# Force line-buffered stdout so prints appear immediately when piped (e.g. | tee)
sys.stdout.reconfigure(line_buffering=True)
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel
from typing import AsyncGenerator, Optional

from .youtube_fetcher import fetch_video_data, fetch_video_metadata, fetch_transcript, extract_video_id, clean_old_cache


def _ts():
    return datetime.now().strftime("[%H:%M:%S]")
from .clickbait_analyzer import analyze_for_clickbait


app = FastAPI(title="YouTube Clickbait Detector")

# Enable CORS for browser extension and local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class AnalyzeRequest(BaseModel):
    """Request body for /analyze endpoint."""
    url: str


@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve the web UI."""
    return HTMLResponse(content=HTMLContent)


async def analyze_stream(url: str) -> AsyncGenerator[str, None]:
    """Stream analysis progress as JSON lines."""

    def send(event: str, data: dict):
        return f"event: {event}\ndata: {json.dumps(data)}\n\n"

    try:
        video_id = extract_video_id(url)
        _t_start = time.monotonic()
        print(f"{_ts()} INFO: [{url}] Processing")

        # Clean old cache entries periodically
        await asyncio.to_thread(clean_old_cache, max_entries=10)

        # Start both metadata fetching and transcription in parallel
        _t_tx = time.monotonic()
        transcript_task = asyncio.create_task(
            asyncio.to_thread(fetch_transcript, video_id, verbose=False)
        )
        try:
            yield send("status", {"message": "Fetching metadata..."})
            print(f"{_ts()} INFO: [{url}] Fetching metadata")
            _t_meta_fetch = time.monotonic()
            metadata = await asyncio.to_thread(fetch_video_metadata, video_id)
            print(f"{_ts()} INFO: [{url}] Fetching metadata [DONE in {round(time.monotonic() - _t_meta_fetch)} sec]")

            # Run metadata analysis
            _meta_bytes = len((metadata['title'] + metadata['description']).encode())
            _t_meta_llm = time.monotonic()
            print(f"{_ts()} INFO: [{url}] Invoking LLM for analysis on metadata ({_meta_bytes} bytes)")
            yield send("status", {"message": "Analyzing metadata..."})

            initial_analysis = await asyncio.to_thread(
                analyze_for_clickbait,
                title=metadata['title'],
                description=metadata['description'],
                transcript=None
            )
            print(f"{_ts()} INFO: [{url}] Invoking LLM for analysis on metadata [DONE in {round(time.monotonic() - _t_meta_llm)} sec]")

            # Send initial result - display immediately
            yield send("initial", {
                "title": metadata['title'],
                "score": initial_analysis.clickbait_score,
                "is_clickbait": initial_analysis.is_clickbait,
                "reasoning": initial_analysis.reasoning,
                "is_live": metadata.get('is_live', False)
            })

            # Check if live stream - skip transcription
            if metadata.get('is_live', False):
                print(f"{_ts()} INFO: [{url}] Live stream detected, skipping transcription")
                yield send("transcript", {
                    "disabled": True,
                    "reason": "Live stream - transcript unavailable"
                })
            else:
                # Wait for transcript to complete
                yield send("status", {"message": "Downloading and transcribing audio..."})
                transcript = await transcript_task
                print(f"{_ts()} INFO: [{url}] Fetching transcript in background [DONE in {round(time.monotonic() - _t_tx)} sec]")

                if transcript:
                    _tx_bytes = len((metadata['title'] + metadata['description'] + transcript).encode())
                    _t_tx_llm = time.monotonic()
                    print(f"{_ts()} INFO: [{url}] Invoking LLM for analysis on transcription ({_tx_bytes} bytes)")
                    yield send("status", {"message": "Transcription complete. Analyzing full content..."})
                    # Full analysis with transcript
                    analysis = await asyncio.to_thread(
                        analyze_for_clickbait,
                        title=metadata['title'],
                        description=metadata['description'],
                        transcript=transcript
                    )
                    print(f"{_ts()} INFO: [{url}] Invoking LLM for analysis on transcription [DONE in {round(time.monotonic() - _t_tx_llm)} sec]")

                    yield send("transcript", {
                        "score": analysis.clickbait_score,
                        "is_clickbait": analysis.is_clickbait,
                        "reasoning": analysis.reasoning
                    })
                else:
                    yield send("error", {"message": "Could not transcribe audio"})

            print(f"{_ts()} INFO: [{url}] Processing [DONE in {round(time.monotonic() - _t_start)} sec]")
            yield send("done", {})
        finally:
            if not transcript_task.done():
                transcript_task.cancel()
    except Exception as e:
        print(f"{_ts()} ERROR: [{url}] {type(e).__name__}: {e}")
        yield send("error", {"message": str(e)})


@app.post("/analyze-stream")
async def analyze_streaming(request: Request):
    """Stream analysis progress via Server-Sent Events."""
    data = await request.json()
    url = data.get("url", "")

    return StreamingResponse(
        analyze_stream(url),
        media_type="text/event-stream"
    )


HTMLContent = """
<!DOCTYPE html>
<html>
<head>
    <title>YouTube Clickbait Detector</title>
    <style>
        * { box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            max-width: 800px;
            margin: 0 auto;
            padding: 40px 20px;
            background: #f5f5f5;
        }
        h1 { color: #333; margin-bottom: 30px; }
        .input-group { display: flex; gap: 10px; margin-bottom: 30px; }
        input[type="text"] {
            flex: 1;
            padding: 12px 16px;
            font-size: 16px;
            border: 2px solid #ddd;
            border-radius: 8px;
            outline: none;
        }
        input[type="text"]:focus { border-color: #007bff; }
        button {
            padding: 12px 24px;
            font-size: 16px;
            background: #007bff;
            color: white;
            border: none;
            border-radius: 8px;
            cursor: pointer;
        }
        button:hover { background: #0056b3; }
        button:disabled { background: #ccc; cursor: not-allowed; }
        .result {
            background: white;
            padding: 24px;
            border-radius: 12px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            margin-bottom: 20px;
        }
        .result h3 { margin-top: 0; color: #555; }
        #metadata-result { border-left: 4px solid #2196F3; }
        #full-result { border-left: 4px solid #4CAF50; }
        .results-container {
            display: flex;
            gap: 20px;
            justify-content: center;
            max-width: 1400px;
            margin: 0 auto;
        }
        .results-container .result {
            flex: 1;
            margin-bottom: 0;
            min-width: 500px;
            max-width: 700px;
        }
        .results-container .result.empty {
            opacity: 0.5;
        }
        .score {
            font-size: 24px;
            font-weight: bold;
            text-align: center;
            padding: 20px;
            border-radius: 8px;
            margin: 20px 0;
            line-height: 1.4;
        }
        .score.clickbait { background: #ffebee; color: #c62828; }
        .score.safe { background: #e8f5e9; color: #2e7d32; }
        .reasoning { white-space: pre-wrap; line-height: 1.6; }
        .status {
            text-align: center;
            padding: 15px;
            color: #666;
            font-size: 14px;
            margin: 10px 0;
        }
        .video-link { margin: 20px 0; }
        .video-link a {
            color: #007bff;
            text-decoration: none;
            font-size: 14px;
        }
        .video-link a:hover { text-decoration: underline; }
            .open-tab-btn {
            padding: 12px 20px;
            font-size: 16px;
            background: #28a745;
            color: white;
            border: none;
            border-radius: 8px;
            cursor: pointer;
        }
        .open-tab-btn:hover { background: #218838; }
    </style>
</head>
<body>
    <h1>YouTube Clickbait Detector</h1>
    <div class="input-group">
        <input type="text" id="url" placeholder="Paste YouTube URL here..." />
        <button onclick="analyze()" id="btn">Clickbait?</button>
        <button class="open-tab-btn" onclick="openInNewTab()">Open in new tab</button>
    </div>
    <div id="statuscontainer"></div>
    <div class="results-container">
        <div class="result" id="metadata-result">
            <h2 id="title"></h2>
            <h3>Metadata Analysis</h3>
            <div class="score" id="metadata-score">Waiting for data...</div>
            <div class="reasoning" id="metadata-reasoning"></div>
        </div>
        <div class="result" id="full-result">
            <h3>Full Analysis (with transcript)</h3>
            <div class="score" id="full-score">Waiting for transcript...</div>
            <div class="reasoning" id="full-reasoning"></div>
        </div>
    </div>
    <script>
        let controller = null;

        function updateStatus(msg) {
            document.getElementById('statuscontainer').innerHTML =
                '<div class="status">' + msg + '</div>';
        }

        function showMetadataResult(title, score, isClickbait, reasoning) {
            document.getElementById('title').textContent = title;
            const scoreEl = document.getElementById('metadata-score');
            scoreEl.textContent = (isClickbait ? 'CLICKBAIT' : 'NOT CLICKBAIT') + ' (' + score + '/100 pts)';
            scoreEl.className = 'score ' + (isClickbait ? 'clickbait' : 'safe');
            document.getElementById('metadata-reasoning').textContent = reasoning;
            document.getElementById('metadata-result').classList.remove('empty');
        }

        function showFullResult(score, isClickbait, reasoning, initialScore) {
            const scoreEl = document.getElementById('full-score');
            scoreEl.textContent = (isClickbait ? 'CLICKBAIT' : 'NOT CLICKBAIT') + ' (' + score + '/100 pts)';
            scoreEl.className = 'score ' + (isClickbait ? 'clickbait' : 'safe');
            document.getElementById('full-reasoning').textContent = reasoning;
            document.getElementById('full-result').classList.remove('empty');
        }

        async function analyze() {
            const url = document.getElementById('url').value;
            const btn = document.getElementById('btn');

            if (!url) { alert('Please enter a URL'); return; }

            console.log('INFO: Analyzing video:', url);

            // Cancel any existing request
            if (controller) controller.abort();
            controller = new AbortController();

            btn.disabled = true;
            document.getElementById('metadata-result').classList.add('empty');
            document.getElementById('full-result').classList.add('empty');
            document.getElementById('metadata-score').textContent = 'Waiting for data...';
            document.getElementById('full-score').textContent = 'Waiting for transcript...';
            document.getElementById('metadata-reasoning').textContent = '';
            document.getElementById('full-reasoning').textContent = '';
            updateStatus('Connecting...');

            try {
                const response = await fetch('/analyze-stream', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ url }),
                    signal: controller.signal
                });

                if (!response.ok) {
                    throw new Error("Server error: " + response.status + " " + response.statusText);
                }

                const reader = response.body.getReader();
                const decoder = new TextDecoder();
                let buffer = '';

                while (true) {
                    const { done, value } = await reader.read();
                    if (done) break;

                    buffer += decoder.decode(value, { stream: true });
                    const parts = buffer.split(String.fromCharCode(10, 10));
                    buffer = parts.pop();

                    for (const part of parts) {
                        if (!part.trim()) continue;

                        const lines = part.split(String.fromCharCode(10));
                        let event = null;
                        let data = null;

                        for (const line of lines) {
                            if (line.startsWith('event: ')) {
                                event = line.slice(7).trim();
                            } else if (line.startsWith('data: ')) {
                                data = line.slice(6).trim();
                            }
                        }

                        if (event && data) {
                            try {
                                const jsonData = JSON.parse(data);

                                if (event === 'status') {
                                    updateStatus(jsonData.message);
                                } else if (event === 'initial') {
                                    showMetadataResult(jsonData.title, jsonData.score, jsonData.is_clickbait, jsonData.reasoning);
                                } else if (event === 'transcript') {
                                    const initialScore = document.getElementById('metadata-score').textContent.match(/\\d+/);
                                    const initialScoreValue = initialScore ? initialScore[0] : '?';
                                    showFullResult(jsonData.score, jsonData.is_clickbait, jsonData.reasoning, initialScoreValue);
                                    updateStatus('');
                                } else if (event === 'error') {
                                    updateStatus('Error: ' + jsonData.message);
                                } else if (event === 'done') {
                                    reader.cancel();
                                }
                            } catch (parseErr) {
                                console.error('Failed to parse JSON:', data, parseErr);
                            }
                        }
                    }
                }
            } catch (err) {
                if (err.name === 'AbortError') {
                    updateStatus('Cancelled by user');
                } else {
                    alert('Error: ' + err.message);
                }
            } finally {
                btn.disabled = false;
            }
        }

        function openInNewTab() {
            const url = document.getElementById('url').value;
            if (url) {
                window.open(url, '_blank');
            }
        }

        document.getElementById('url').addEventListener('keypress', (e) => {
            if (e.key === 'Enter') analyze();
        });
    </script>
</body>
</html>
"""


_UVICORN_LOG_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {
            "()": "uvicorn.logging.DefaultFormatter",
            "fmt": "[%(asctime)s] %(levelprefix)s %(message)s",
            "datefmt": "%H:%M:%S",
            "use_colors": None,
        },
        "access": {
            "()": "uvicorn.logging.AccessFormatter",
            "fmt": '[%(asctime)s] %(levelprefix)s %(client_addr)s - "%(request_line)s" %(status_code)s',
            "datefmt": "%H:%M:%S",
        },
    },
    "handlers": {
        "default": {"formatter": "default", "class": "logging.StreamHandler", "stream": "ext://sys.stderr"},
        "access": {"formatter": "access", "class": "logging.StreamHandler", "stream": "ext://sys.stdout"},
    },
    "loggers": {
        "uvicorn": {"handlers": ["default"], "level": "INFO", "propagate": False},
        "uvicorn.error": {"level": "INFO"},
        "uvicorn.access": {"handlers": ["access"], "level": "INFO", "propagate": False},
    },
}


def run_server(host: str = "0.0.0.0", port: int = 4004):
    """Run the web server."""
    import uvicorn
    uvicorn.run(app, host=host, port=port, log_config=_UVICORN_LOG_CONFIG)

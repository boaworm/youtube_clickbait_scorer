"""Simple web UI for YouTube clickbait analysis."""

import os
import asyncio
import json
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel
from typing import AsyncGenerator

from .youtube_fetcher import fetch_video_data
from .clickbait_analyzer import analyze_for_clickbait


app = FastAPI(title="YouTube Clickbait Detector")


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
        # Step 1: Fetch metadata
        yield send("status", {"message": "Fetching metadata..."})
        video_data = fetch_video_data(url, verbose=False)

        # Step 2: Initial analysis (metadata only)
        yield send("status", {"message": "Analyzing metadata..."})
        initial_analysis = analyze_for_clickbait(
            title=video_data['title'],
            description=video_data['description'],
            transcript=None
        )

        # Send initial result
        yield send("initial", {
            "title": video_data['title'],
            "score": initial_analysis.clickbait_score,
            "is_clickbait": initial_analysis.is_clickbait,
            "reasoning": initial_analysis.reasoning
        })

        # Step 3: Fetch transcript if needed
        if not video_data['transcript']:
            yield send("status", {"message": "Downloading and transcribing audio..."})
            video_data = fetch_video_data(url, verbose=False)

            if video_data['transcript']:
                yield send("status", {"message": "Transcription complete. Analyzing full content..."})
                # Step 4: Full analysis with transcript
                analysis = analyze_for_clickbait(
                    title=video_data['title'],
                    description=video_data['description'],
                    transcript=video_data['transcript']
                )

                yield send("transcript", {
                    "score": analysis.clickbait_score,
                    "is_clickbait": analysis.is_clickbait,
                    "reasoning": analysis.reasoning
                })
            else:
                yield send("error", {"message": "Could not transcribe audio"})
        else:
            # Transcript already available
            yield send("status", {"message": "Using cached transcript. Analyzing full content..."})
            analysis = analyze_for_clickbait(
                title=video_data['title'],
                description=video_data['description'],
                transcript=video_data['transcript']
            )

            yield send("transcript", {
                "score": analysis.clickbait_score,
                "is_clickbait": analysis.is_clickbait,
                "reasoning": analysis.reasoning
            })

        yield send("done", {})
    except Exception as e:
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
            display: none;
            margin-bottom: 20px;
        }
        .result.show { display: block; }
        .result h2 { margin-top: 0; }
        .score {
            font-size: 48px;
            font-weight: bold;
            text-align: center;
            padding: 20px;
            border-radius: 8px;
            margin: 20px 0;
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
        .skip-btn {
            margin-top: 15px;
            padding: 8px 16px;
            font-size: 14px;
            background: #6c757d;
            color: white;
            border: none;
            border-radius: 6px;
            cursor: pointer;
        }
        .skip-btn:hover { background: #5a6268; }
    </style>
</head>
<body>
    <h1>YouTube Clickbait Detector</h1>
    <div class="input-group">
        <input type="text" id="url" placeholder="Paste YouTube URL here..." />
        <button onclick="analyze()" id="btn">Clickbait?</button>
    </div>
    <div class="video-link" id="videolinkcontainer" style="display:none; margin: 20px 0;">
        <a id="videolink" href="" target="_blank"></a>
    </div>
    <div id="statuscontainer"></div>
    <div class="result" id="result">
        <h2 id="title"></h2>
        <div class="score" id="score"></div>
        <div class="reasoning" id="reasoning"></div>
        <button class="skip-btn" id="skipbtn" onclick="skipTranscription()" style="display:none;">
            Skip transcription - use this result
        </button>
    </div>
    <script>
        let controller = null;

        function updateStatus(msg) {
            document.getElementById('statuscontainer').innerHTML =
                '<div class="status">' + msg + '</div>';
        }

        function showResult(title, score, isClickbait, reasoning) {
            document.getElementById('title').textContent = title;
            const scoreEl = document.getElementById('score');
            scoreEl.textContent = score + '% ' + (isClickbait ? 'CLICKBAIT' : 'NOT CLICKBAIT');
            scoreEl.className = 'score ' + (isClickbait ? 'clickbait' : 'safe');
            document.getElementById('reasoning').textContent = reasoning;
            document.getElementById('result').classList.add('show');
        }

        async function analyze() {
            const url = document.getElementById('url').value;
            const btn = document.getElementById('btn');
            const linkContainer = document.getElementById('videolinkcontainer');
            const linkEl = document.getElementById('videolink');

            if (!url) { alert('Please enter a URL'); return; }

            // Cancel any existing request
            if (controller) controller.abort();
            controller = new AbortController();

            document.getElementById('skipbtn').style.display = 'none';

            linkEl.href = url;
            linkEl.textContent = url;
            linkContainer.style.display = 'block';

            btn.disabled = true;
            document.getElementById('result').classList.remove('show');
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
                                    showResult(jsonData.title, jsonData.score, jsonData.is_clickbait, jsonData.reasoning);
                                    document.getElementById('skipbtn').style.display = 'inline-block';
                                } else if (event === 'transcript') {
                                    showResult(document.getElementById('title').textContent, jsonData.score, jsonData.is_clickbait, jsonData.reasoning);
                                    document.getElementById('skipbtn').style.display = 'none';
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

        function skipTranscription() {
            if (controller) controller.abort();
            document.getElementById('skipbtn').style.display = 'none';
            updateStatus('Using metadata-only analysis');
            document.getElementById('btn').disabled = false;
        }

        document.getElementById('url').addEventListener('keypress', (e) => {
            if (e.key === 'Enter') analyze();
        });
    </script>
</body>
</html>
"""


def run_server(host: str = "0.0.0.0", port: int = 4004):
    """Run the web server."""
    import uvicorn
    uvicorn.run(app, host=host, port=port)

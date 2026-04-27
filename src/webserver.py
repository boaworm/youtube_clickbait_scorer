"""Simple web UI for YouTube clickbait analysis."""

import os
from pathlib import Path
from fastapi import FastAPI
from fastapi.responses import JSONResponse, HTMLResponse
from pydantic import BaseModel

from .youtube_fetcher import fetch_video_data
from .clickbait_analyzer import analyze_for_clickbait


app = FastAPI(title="YouTube Clickbait Detector")


class AnalyzeRequest(BaseModel):
    """Request body for /analyze endpoint."""
    url: str


class AnalyzeResponse(BaseModel):
    """Response body for /analyze endpoint."""
    title: str
    description: str
    initial_score: int
    transcription_score: int
    is_clickbait: bool
    reasoning: str
    transcript: str | None = None


@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve the web UI."""
    return HTMLContent


@app.post("/analyze", response_model=AnalyzeResponse)
async def analyze(request: AnalyzeRequest):
    """Analyze a YouTube video for clickbait."""
    # Fetch video data
    video_data = fetch_video_data(request.url, verbose=False)

    # Initial analysis (metadata only)
    initial_analysis = analyze_for_clickbait(
        title=video_data['title'],
        description=video_data['description'],
        transcript=None
    )

    # If no transcript, fetch with transcription
    if not video_data['transcript']:
        video_data = fetch_video_data(request.url, verbose=False)

    # Full analysis
    if video_data['transcript']:
        analysis = analyze_for_clickbait(
            title=video_data['title'],
            description=video_data['description'],
            transcript=video_data['transcript']
        )
    else:
        analysis = initial_analysis

    return AnalyzeResponse(
        title=video_data['title'],
        description=video_data['description'],
        initial_score=initial_analysis.clickbait_score,
        transcription_score=analysis.clickbait_score,
        is_clickbait=analysis.is_clickbait,
        reasoning=analysis.reasoning,
        transcript=video_data['transcript']
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
        .loading { text-align: center; padding: 40px; color: #666; }
    </style>
</head>
<body>
    <h1>YouTube Clickbait Detector</h1>
    <div class="input-group">
        <input type="text" id="url" placeholder="Paste YouTube URL here..." />
        <button onclick="analyze()" id="btn">Clickbait?</button>
    </div>
    <div class="loading" id="loading" style="display:none;">Analyzing...</div>
    <div class="result" id="result">
        <h2 id="title"></h2>
        <div class="score" id="score"></div>
        <div class="reasoning" id="reasoning"></div>
    </div>
    <script>
        async function analyze() {
            const url = document.getElementById('url').value;
            const btn = document.getElementById('btn');
            const loading = document.getElementById('loading');
            const result = document.getElementById('result');

            if (!url) { alert('Please enter a URL'); return; }

            btn.disabled = true;
            loading.style.display = 'block';
            result.classList.remove('show');

            try {
                const res = await fetch('/analyze', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ url })
                });
                const data = await res.json();

                document.getElementById('title').textContent = data.title;
                const scoreEl = document.getElementById('score');
                scoreEl.textContent = `${data.transcription_score}% ${data.is_clickbait ? 'CLICKBAIT' : 'NOT CLICKBAIT'}`;
                scoreEl.className = 'score ' + (data.is_clickbait ? 'clickbait' : 'safe');
                document.getElementById('reasoning').textContent = data.reasoning;

                result.classList.add('show');
            } catch (err) {
                alert('Error: ' + err.message);
            } finally {
                btn.disabled = false;
                loading.style.display = 'none';
            }
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

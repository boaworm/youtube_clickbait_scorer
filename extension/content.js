// YouTube Clickbait Detector - Content Script
// Runs on YouTube pages, injects UI and handles user interactions

let currentController = null;
let isPanelInjected = false;

// Detect video ID from current URL
function getVideoId() {
  const urlParams = new URLSearchParams(window.location.search);
  return urlParams.get('v');
}

// Get current video URL
function getVideoUrl() {
  return window.location.href;
}

// Inject the clickbait detector panel
function injectPanel() {
  if (isPanelInjected) return;

  // Find the video player container
  const videoContainer = document.querySelector('ytd-watch-flexy');
  if (!videoContainer) return;

  // Create panel HTML
  const panel = document.createElement('div');
  panel.id = 'clickbait-detector-panel';
  panel.innerHTML = `
    <div class="cdp-header">
      <h3>Clickbait Detector</h3>
      <button id="cdp-analyze-btn">Clickbait?</button>
    </div>
    <div id="cdp-status" class="cdp-status"></div>
    <div class="cdp-results">
      <div id="cdp-metadata" class="cdp-result-box">
        <h4>Metadata Analysis</h4>
        <div id="cdp-metadata-score" class="cdp-score">Waiting...</div>
        <div id="cdp-metadata-reasoning" class="cdp-reasoning"></div>
      </div>
      <div id="cdp-full" class="cdp-result-box">
        <h4>Full Analysis (with transcript)</h4>
        <div id="cdp-full-score" class="cdp-score">Waiting...</div>
        <div id="cdp-full-reasoning" class="cdp-reasoning"></div>
      </div>
    </div>
  `;

  // Insert panel below video info
  const videoInfo = document.querySelector('#below-overlap-container') ||
                    document.querySelector('#movie_player')?.parentElement;
  if (videoInfo) {
    videoInfo.insertBefore(panel, videoInfo.firstChild);
    isPanelInjected = true;
  }

  // Add event listener
  const analyzeBtn = document.getElementById('cdp-analyze-btn');
  if (analyzeBtn) {
    analyzeBtn.addEventListener('click', handleAnalyze);
  }
}

// Handle analyze button click
async function handleAnalyze() {
  const videoId = getVideoId();
  if (!videoId) {
    updateStatus('No video ID found');
    return;
  }

  const url = getVideoUrl();
  console.log('INFO: Analyzing video:', url);

  // Reset panel state
  resetPanel();
  updateStatus('Connecting...');

  // Cancel any existing request
  if (currentController) {
    currentController.abort();
  }
  currentController = new AbortController();

  try {
    const response = await fetch('http://localhost:4004/analyze-stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url }),
      signal: currentController.signal
    });

    if (!response.ok) {
      throw new Error(`Server error: ${response.status}`);
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const parts = buffer.split('\n\n');
      buffer = parts.pop();

      for (const part of parts) {
        if (!part.trim()) continue;

        const lines = part.split('\n');
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
              showFullResult(jsonData.score, jsonData.is_clickbait, jsonData.reasoning);
              updateStatus('');
            } else if (event === 'error') {
              updateStatus('Error: ' + jsonData.message);
            }
          } catch (parseErr) {
            console.error('Failed to parse SSE data:', parseErr);
          }
        }
      }
    }
  } catch (err) {
    if (err.name === 'AbortError') {
      updateStatus('Cancelled');
    } else {
      updateStatus('Error: ' + err.message);
    }
  }
}

function resetPanel() {
  document.getElementById('cdp-metadata-score').textContent = 'Waiting...';
  document.getElementById('cdp-metadata-score').className = 'cdp-score';
  document.getElementById('cdp-metadata-reasoning').textContent = '';
  document.getElementById('cdp-full-score').textContent = 'Waiting...';
  document.getElementById('cdp-full-score').className = 'cdp-score';
  document.getElementById('cdp-full-reasoning').textContent = '';
}

function updateStatus(message) {
  const statusEl = document.getElementById('cdp-status');
  if (statusEl) {
    statusEl.textContent = message;
  }
}

function showMetadataResult(title, score, isClickbait, reasoning) {
  const scoreEl = document.getElementById('cdp-metadata-score');
  const reasoningEl = document.getElementById('cdp-metadata-reasoning');

  scoreEl.textContent = (isClickbait ? 'CLICKBAIT' : 'NOT CLICKBAIT') + ' (' + score + '/100 pts)';
  scoreEl.className = 'cdp-score ' + (isClickbait ? 'clickbait' : 'safe');
  reasoningEl.textContent = reasoning;
}

function showFullResult(score, isClickbait, reasoning) {
  const scoreEl = document.getElementById('cdp-full-score');
  const reasoningEl = document.getElementById('cdp-full-reasoning');

  scoreEl.textContent = (isClickbait ? 'CLICKBAIT' : 'NOT CLICKBAIT') + ' (' + score + '/100 pts)';
  scoreEl.className = 'cdp-score ' + (isClickbait ? 'clickbait' : 'safe');
  reasoningEl.textContent = reasoning;
}

// Observe DOM changes to detect page navigation
function setupObserver() {
  const observer = new MutationObserver((mutations) => {
    for (const mutation of mutations) {
      if (mutation.type === 'childList' && mutation.addedNodes.length > 0) {
        // Check if we're on a video page
        if (getVideoId() && !isPanelInjected) {
          injectPanel();
        }
      }
    }
  });

  observer.observe(document.body, { childList: true, subtree: true });
}

// Initialize
if (getVideoId()) {
  injectPanel();
}
setupObserver();

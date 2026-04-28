// YouTube Clickbait Detector - Content Script
// Runs on YouTube pages, injects UI and handles user interactions

const DEFAULT_BACKEND_URL = 'http://localhost:4004';

let currentController = null;
let isPanelInjected = false;

function getBackendUrl() {
  return new Promise((resolve) => {
    chrome.storage.sync.get(['backendUrl'], (result) => {
      resolve(result.backendUrl || DEFAULT_BACKEND_URL);
    });
  });
}

// Detect video ID from current URL
function getVideoId() {
  const urlParams = new URLSearchParams(window.location.search);
  return urlParams.get('v');
}

// Get current video URL
function getVideoUrl() {
  return window.location.href;
}

// Extract video ID from a thumbnail link
function getVideoIdFromElement(el) {
  // Try multiple possible link selectors
  const link = el.querySelector('a#video-title, a#thumbnail, a[href*="v="]');
  if (link) {
    const href = link.href;
    console.log('[Clickbait] Found link:', href);
    // Extract video ID from URL like /watch?v=VIDEO_ID
    const match = href.match(/[?&]v=([^&]+)/);
    if (match && match[1]) {
      console.log('[Clickbait] Extracted video ID:', match[1]);
      return match[1];
    }
  }
  console.log('[Clickbait] No link found in element');
  return null;
}

// Get video URL from element
function getVideoUrlFromElement(el) {
  const link = el.querySelector('a#video-title, a#thumbnail, a[href*="v="]');
  if (link) {
    return link.href;
  }
  return null;
}

// Inject click button and result indicators on video thumbnails
function injectButtonsOnThumbnails() {
  const selectors = [
    'ytd-video-renderer',
    'ytd-grid-video-renderer',
    '#contents ytd-video-renderer',
    '#contents ytd-grid-video-renderer',
    'ytd-rich-item-renderer',
    '#contents ytd-rich-item-renderer'
  ];

  let videos = document.querySelectorAll(selectors.join(', '));
  console.log('[Clickbait] Found', videos.length, 'video thumbnails');

  videos.forEach(video => {
    if (!video.querySelector('.cdp-results-inline')) {
      // Create results container
      const resultsDiv = document.createElement('div');
      resultsDiv.className = 'cdp-results-inline';
      resultsDiv.innerHTML = `
        <button class="cdp-thumb-btn">Clickbait?</button>
        <span class="cdp-result cdp-metadata-result">Metadata: --</span>
        <span class="cdp-result cdp-full-result">Transcript: --</span>
      `;

      // Insert at the top of the video renderer to avoid being covered
      video.insertBefore(resultsDiv, video.firstChild);

      // Add click handler
      const button = resultsDiv.querySelector('.cdp-thumb-btn');
      button.addEventListener('click', () => {
        const videoId = getVideoIdFromElement(video);
        const videoUrl = getVideoUrlFromElement(video);
        if (videoId && videoUrl) {
          console.log('[Clickbait] Analyzing:', videoUrl);
          handleAnalyzeInline(videoUrl, resultsDiv);
        } else {
          console.log('[Clickbait] Could not extract video ID');
        }
      });
    }
  });
}

// Inject the clickbait detector panel on video watch page
function injectWatchPanel() {
  if (isPanelInjected) return;

  const playerContainer = document.querySelector('#movie_player');
  const infoContainer = document.querySelector('#meta-outer');

  if (!playerContainer && !infoContainer) {
    return;
  }

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

  const targetContainer = infoContainer || playerContainer?.parentElement;
  if (targetContainer) {
    targetContainer.insertBefore(panel, targetContainer.firstChild);
    console.log('[Clickbait] Watch panel injected');
    isPanelInjected = true;
  }

  const analyzeBtn = document.getElementById('cdp-analyze-btn');
  if (analyzeBtn) {
    analyzeBtn.addEventListener('click', () => handleAnalyze(getVideoUrl()));
  }
}

// Main inject function
function injectPanel() {
  injectButtonsOnThumbnails();
  injectWatchPanel();
}

// Handle analyze for inline thumbnail results
async function handleAnalyzeInline(url, resultsDiv) {
  const metadataResult = resultsDiv.querySelector('.cdp-metadata-result');
  const fullResult = resultsDiv.querySelector('.cdp-full-result');

  // Set loading states with animation
  metadataResult.textContent = 'Metadata: ...';
  metadataResult.classList.add('cdp-loading');
  fullResult.classList.add('cdp-loading');

  console.log('INFO: Analyzing video:', url);

  // Cancel any existing request
  if (currentController) {
    currentController.abort();
  }
  currentController = new AbortController();

  try {
    const backendUrl = await getBackendUrl();
    const response = await fetch(backendUrl + '/analyze-stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url }),
      signal: currentController.signal
    });

    if (!response.ok) {
      throw new Error('Server error: ' + response.status);
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
        let eventName = null;
        let data = null;

        for (const line of lines) {
          if (line.startsWith('event: ')) {
            eventName = line.slice(7).trim();
          } else if (line.startsWith('data: ')) {
            data = line.slice(6).trim();
          }
        }

        if (eventName && data) {
          try {
            const jsonData = JSON.parse(data);

            if (eventName === 'initial') {
              const liveBadge = jsonData.is_live ? ' 🟢 LIVE' : '';
              const text = (jsonData.is_clickbait ? 'CLICKBAIT' : 'OK') + ' (' + jsonData.score + '/100)' + liveBadge;
              metadataResult.textContent = 'Metadata: ' + text;
              metadataResult.classList.remove('cdp-loading');
              metadataResult.className = 'cdp-result cdp-metadata-result ' + (jsonData.is_clickbait ? 'cdp-bad' : 'cdp-good');
              // Store full reasoning for tooltip
              metadataResult.dataset.reasoning = jsonData.reasoning;
              metadataResult.title = jsonData.reasoning;
            } else if (eventName === 'transcript') {
              console.log('[Clickbait] Transcript event received:', jsonData);
              if (jsonData.disabled) {
                fullResult.textContent = 'Transcript: Disabled - Live';
                fullResult.classList.remove('cdp-loading');
                fullResult.className = 'cdp-result cdp-full-result cdp-disabled';
                fullResult.title = jsonData.reason;
              } else {
                const text = (jsonData.is_clickbait ? 'CLICKBAIT' : 'OK') + ' (' + jsonData.score + '/100)';
                fullResult.textContent = 'Transcript: ' + text;
                fullResult.classList.remove('cdp-loading');
                fullResult.className = 'cdp-result cdp-full-result ' + (jsonData.is_clickbait ? 'cdp-bad' : 'cdp-good');
                fullResult.dataset.reasoning = jsonData.reasoning;
                fullResult.title = jsonData.reasoning;
              }
            } else if (eventName === 'error') {
              metadataResult.textContent = 'Error: ' + jsonData.message;
            }
          } catch (parseErr) {
            console.error('Failed to parse SSE data:', parseErr);
          }
        }
      }
    }
  } catch (err) {
    if (err.name !== 'AbortError') {
      metadataResult.textContent = 'Error: ' + err.message;
    }
  }
}

// Handle analyze for watch page panel
async function handleAnalyze(url) {
  console.log('INFO: Analyzing video:', url);

  // Reset panel state
  const metadataScore = document.getElementById('cdp-metadata-score');
  const metadataReasoning = document.getElementById('cdp-metadata-reasoning');
  const fullScore = document.getElementById('cdp-full-score');
  const fullReasoning = document.getElementById('cdp-full-reasoning');

  if (metadataScore) metadataScore.textContent = 'Waiting...';
  if (metadataReasoning) metadataReasoning.textContent = '';
  if (fullScore) fullScore.textContent = 'Waiting...';
  if (fullReasoning) fullReasoning.textContent = '';

  updateStatus('Connecting...');

  // Cancel any existing request
  if (currentController) {
    currentController.abort();
  }
  currentController = new AbortController();

  try {
    const backendUrl = await getBackendUrl();
    const response = await fetch(backendUrl + '/analyze-stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url }),
      signal: currentController.signal
    });

    if (!response.ok) {
      throw new Error('Server error: ' + response.status);
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
        let eventName = null;
        let data = null;

        for (const line of lines) {
          if (line.startsWith('event: ')) {
            eventName = line.slice(7).trim();
          } else if (line.startsWith('data: ')) {
            data = line.slice(6).trim();
          }
        }

        if (eventName && data) {
          try {
            const jsonData = JSON.parse(data);

            if (eventName === 'status') {
              updateStatus(jsonData.message);
            } else if (eventName === 'initial') {
              showMetadataResult(jsonData.title, jsonData.score, jsonData.is_clickbait, jsonData.reasoning, jsonData.is_live);
            } else if (eventName === 'transcript') {
              if (jsonData.disabled) {
                showFullResultDisabled(jsonData.reason);
              } else {
                showFullResult(jsonData.score, jsonData.is_clickbait, jsonData.reasoning);
              }
              updateStatus('');
            } else if (eventName === 'error') {
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

function showMetadataResult(title, score, isClickbait, reasoning, isLive = false) {
  const scoreEl = document.getElementById('cdp-metadata-score');
  const reasoningEl = document.getElementById('cdp-metadata-reasoning');

  const liveBadge = isLive ? ' 🟢 LIVE' : '';
  scoreEl.textContent = (isClickbait ? 'CLICKBAIT' : 'NOT CLICKBAIT') + ' (' + score + '/100 pts)' + liveBadge;
  scoreEl.className = 'cdp-score ' + (isClickbait ? 'clickbait' : 'safe');
  if (isLive) {
    scoreEl.classList.add('cdp-live');
  }
  reasoningEl.textContent = reasoning;
}

function showFullResult(score, isClickbait, reasoning) {
  const scoreEl = document.getElementById('cdp-full-score');
  const reasoningEl = document.getElementById('cdp-full-reasoning');

  scoreEl.textContent = (isClickbait ? 'CLICKBAIT' : 'NOT CLICKBAIT') + ' (' + score + '/100 pts)';
  scoreEl.className = 'cdp-score ' + (isClickbait ? 'clickbait' : 'safe');
  reasoningEl.textContent = reasoning;
}

function showFullResultDisabled(reason) {
  const scoreEl = document.getElementById('cdp-full-score');
  const reasoningEl = document.getElementById('cdp-full-reasoning');

  scoreEl.textContent = 'Disabled - Live Stream';
  scoreEl.className = 'cdp-score cdp-disabled';
  reasoningEl.textContent = reason;
}

// Observe DOM changes to detect page navigation and new videos
function setupObserver() {
  const observer = new MutationObserver((mutations) => {
    for (const mutation of mutations) {
      if (mutation.type === 'childList' && mutation.addedNodes.length > 0) {
        const videoId = getVideoId();
        if (videoId && !isPanelInjected) {
          console.log('[Clickbait] Detected video page, injecting panel');
          injectPanel();
        }
        // Also inject buttons on any newly loaded video thumbnails
        injectButtonsOnThumbnails();
      }
    }
  });

  observer.observe(document.body, { childList: true, subtree: true });
}

// Initialize
console.log('[Clickbait] Content script loaded, videoId:', getVideoId());
if (getVideoId()) {
  console.log('[Clickbait] Detected video page, injecting panel');
  injectPanel();
} else {
  console.log('[Clickbait] Homepage or other page, injecting thumbnail buttons');
  injectButtonsOnThumbnails();
}
setupObserver();

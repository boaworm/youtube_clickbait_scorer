# Plan: Allow Concurrent Video Analysis

## Context

The user noticed that clicking "Clickbait?" on a second thumbnail cancels the first analysis. The root cause is a single global `currentController` in the extension that is shared across all thumbnail requests — every new click aborts the previous one.

The backend (FastAPI + Uvicorn) already handles concurrent requests correctly with no shared state, so it needs no changes for basic concurrency. The fix is entirely in the extension.

An optional backend improvement (cancelling wasted server work on early client disconnect) is also included.

---

## Changes

### 1. Extension — `extension/content.js` (primary fix)

**Delete** the global `currentController` variable (line 6):
```js
let currentController = null;  // DELETE THIS
```

**Replace** the cancel/create block in `handleAnalyzeInline` (lines 152–163) to be per-`resultsDiv`:

```js
// Before:
if (currentController) {
  currentController.abort();
}
currentController = new AbortController();
// ...
signal: currentController.signal

// After:
if (resultsDiv._abortController) {
  resultsDiv._abortController.abort();
}
resultsDiv._abortController = new AbortController();
// ...
signal: resultsDiv._abortController.signal
```

This scopes the abort controller to each thumbnail's `resultsDiv` DOM element. Re-clicking the same thumbnail cancels and restarts that specific analysis; clicking a different thumbnail leaves the first one running. The watch page panel works correctly for free since it also passes its own `resultsDiv`.

### 2. Backend — `src/webserver.py` (optional, low-risk improvement)

Add a `try/finally` around the transcript task in `analyze_stream` (~line 55) to cancel wasted work when the client disconnects before the transcript phase starts:

```python
transcript_task = asyncio.create_task(
    asyncio.to_thread(fetch_transcript, video_id, verbose=False)
)
try:
    # ... rest of generator (metadata fetch, initial LLM, await transcript_task, full LLM) ...
finally:
    if not transcript_task.done():
        transcript_task.cancel()
```

Note: this prevents a yt-dlp download+Whisper job from starting if the client disconnects early. It cannot interrupt a Whisper job already in progress (Python threads aren't cancellable), but it avoids the waste in the common re-click case.

---

## Verification

1. Open YouTube homepage
2. Click "Clickbait?" on thumbnail A — confirm it starts loading
3. Immediately click "Clickbait?" on thumbnail B — confirm A **continues** loading while B starts
4. Re-click thumbnail A's button — confirm A restarts (old request cancelled, new one begins)
5. Check browser devtools Network tab to confirm two concurrent SSE streams when clicking two different thumbnails

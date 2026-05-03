# YouTube Clickbait Detector - Browser Extension

A Chrome/Vivaldi extension that analyzes YouTube videos for clickbait titles.

## Requirements

A backend service must be running on `http://localhost:4004`. You can use the
reference implementation from this repo:

```bash
cd ..
python -m src.main --webserver
```

Or any compatible service that exposes the `/analyze-stream` endpoint.

### 2. Load the Extension

1. Open Chrome/Vivaldi and go to `chrome://extensions/`
2. Enable "Developer mode" (toggle in top-right corner)
3. Click "Load unpacked"
4. Select the `extension/` folder inside this project

### 3. Use the Extension

1. Navigate to any YouTube video page
2. A "Clickbait Detector" panel will appear below the video player
3. Click the "Clickbait?" button to analyze
4. View metadata analysis (quick) and full transcription analysis (slower)

## Troubleshooting

### Extension doesn't appear on YouTube
- Make sure you're on a video page (URL contains `?v=`)
- Refresh the page after loading the extension
- Check `chrome://extensions/` for any error messages

### "Server error" when clicking analyze
- Verify the backend is running: `python -m src.main --webserver`
- Check that the server is accessible at `http://localhost:4004`
- Look at the browser console (F12) for error details

### CORS errors
- The extension is configured to access `localhost:4004`
- Ensure the backend has CORS enabled (it does by default in FastAPI)

## Files

- `manifest.json` - Extension configuration
- `content.js` - Runs on YouTube pages, injects UI
- `background.js` - Service worker (required for manifest v3)
- `styles.css` - Panel styling

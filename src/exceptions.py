"""Custom exceptions for YouTube clickbait detector."""


class YouTubeFetchError(Exception):
    """Base exception for YouTube fetching errors."""
    pass


class MetadataExtractionError(YouTubeFetchError):
    """Failed to extract video metadata."""
    def __init__(self, video_id: str, message: str):
        self.video_id = video_id
        self.message = message
        super().__init__(f"Metadata extraction failed for {video_id}: {message}")


class DownloadError(YouTubeFetchError):
    """Failed to download video."""
    def __init__(self, url: str, message: str, retry_count: int = 0):
        self.url = url
        self.retry_count = retry_count
        super().__init__(f"Download failed for {url}: {message}")


class ExtractionError(YouTubeFetchError):
    """Failed to extract audio from video."""
    def __init__(self, video_path: str, message: str):
        self.video_path = video_path
        self.message = message
        super().__init__(f"Audio extraction failed for {video_path}: {message}")


class TranscriptionError(YouTubeFetchError):
    """Failed to transcribe audio."""
    def __init__(self, audio_path: str, message: str):
        self.audio_path = audio_path
        self.message = message
        super().__init__(f"Transcription failed for {audio_path}: {message}")


class FallbackExhaustedError(YouTubeFetchError):
    """All fallback methods failed."""
    def __init__(self, video_id: str, failures: list[dict]):
        self.video_id = video_id
        self.failures = failures
        message = self._build_message(failures)
        super().__init__(message)

    def _build_message(self, failures: list[dict]) -> str:
        parts = []
        for i, f in enumerate(failures, 1):
            parts.append(f"{i}. {f['method']}: {f['error']}")
        return f"All transcript methods failed for video:\n" + "\n".join(parts)

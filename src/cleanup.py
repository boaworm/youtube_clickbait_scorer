"""Manage temporary files for video processing."""

import shutil
import os
from pathlib import Path
from typing import Optional
from contextlib import contextmanager


class TempFileManager:
    """Manage temporary files for video processing."""

    def __init__(self, base_dir: Optional[Path] = None):
        """
        Initialize temp file manager.

        Args:
            base_dir: Base directory for temp files.
                     Defaults to project's tmp/ directory.
        """
        self.base_dir = base_dir or Path(__file__).parent.parent / "tmp"
        self.created_files: list[Path] = []
        self.created_dirs: list[Path] = []

    def ensure_base_dir(self) -> Path:
        """Ensure the base directory exists."""
        self.base_dir.mkdir(parents=True, exist_ok=True)
        return self.base_dir

    def create_temp_dir(self, prefix: str = "yt_") -> Path:
        """
        Create a temporary directory in the base directory.

        Args:
            prefix: Directory name prefix

        Returns:
            Path to created directory
        """
        self.ensure_base_dir()
        import tempfile
        temp_dir = tempfile.mkdtemp(prefix=prefix, dir=self.base_dir)
        path = Path(temp_dir)
        self.created_dirs.append(path)
        return path

    def register_file(self, path: Path):
        """Register a file for later cleanup."""
        self.created_files.append(path)

    def register_dir(self, path: Path):
        """Register a directory for later cleanup."""
        self.created_dirs.append(path)

    def cleanup(self):
        """Clean up registered temp files and directories."""
        # Clean files first
        for file_path in self.created_files:
            try:
                if file_path.exists():
                    file_path.unlink()
            except Exception:
                pass  # Ignore cleanup errors

        # Then clean directories (reverse order for nested dirs)
        for dir_path in reversed(self.created_dirs):
            try:
                if dir_path.exists():
                    shutil.rmtree(dir_path)
            except Exception:
                pass  # Ignore cleanup errors

        self.created_files.clear()
        self.created_dirs.clear()

    def cleanup_old_files(self, max_age_hours: int = 24) -> int:
        """
        Clean up files older than specified age.

        Args:
            max_age_hours: Maximum age in hours

        Returns:
            Number of files/directories cleaned up
        """
        import time

        if not self.base_dir.exists():
            return 0

        cutoff_time = time.time() - (max_age_hours * 3600)
        cleaned_count = 0

        for item in self.base_dir.iterdir():
            try:
                if item.is_dir():
                    # Check if directory is old
                    if item.stat().st_mtime < cutoff_time:
                        shutil.rmtree(item)
                        cleaned_count += 1
                elif item.is_file():
                    if item.stat().st_mtime < cutoff_time:
                        item.unlink()
                        cleaned_count += 1
            except Exception:
                pass  # Ignore cleanup errors

        return cleaned_count


@contextmanager
def video_processing_context(video_id: str, temp_dir: Optional[Path] = None):
    """
    Context manager for video processing with automatic cleanup.

    Usage:
        with video_processing_context(video_id) as ctx:
            ctx.video_dir = download_video(url)
            ctx.audio_file = extract_audio(ctx.video_dir)
            transcript = transcribe(ctx.audio_file)
            return transcript

    Temp files are automatically deleted when exiting context.

    Args:
        video_id: Video ID for naming the temp directory
        temp_dir: Optional base temp directory

    Yields:
        TempFileManager instance
    """
    manager = TempFileManager(temp_dir)

    # Create a subdirectory for this video
    video_dir = manager.create_temp_dir(prefix=f"{video_id}_")

    # Attach video_dir to manager for convenience
    manager.video_dir = video_dir

    try:
        yield manager
    finally:
        manager.cleanup()

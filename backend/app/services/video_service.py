"""
Video validation service — validates uploaded files and downloaded media.
"""
from __future__ import annotations
import os
import mimetypes
from pathlib import Path
from app.core.config import get_settings
from app.core.constants import ALLOWED_VIDEO_EXTENSIONS, ALLOWED_VIDEO_MIMETYPES
from app.core.exceptions import (
    InvalidVideoError, VideoTooLargeError, VideoTooLongError
)
from app.services.ffmpeg_service import get_video_info
from app.core.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()

# Common video magic bytes
VIDEO_SIGNATURES = {
    b"\x00\x00\x00\x18ftyp": "mp4",
    b"\x00\x00\x00\x1cftyp": "mp4",
    b"\x00\x00\x00\x20ftyp": "mp4",
    b"ftyp": "mp4",
    b"\x1aE\xdf\xa3": "mkv/webm",
    b"RIFF": "avi",
}


def _check_magic(data: bytes) -> bool:
    """Basic magic byte check for video files."""
    if len(data) < 12:
        return False
    for sig in VIDEO_SIGNATURES:
        if sig in data[:32]:
            return True
    return False


def validate_video_file(
    file_path: str,
    original_filename: str = "",
    size_bytes: int = 0,
    content_type: str = "",
) -> dict:
    """
    Validate a video file. Returns dict with metadata.
    Raises appropriate exceptions on failure.
    """
    # 1. Extension check
    ext = Path(original_filename).suffix.lower() if original_filename else Path(file_path).suffix.lower()
    if ext and ext not in ALLOWED_VIDEO_EXTENSIONS:
        raise InvalidVideoError(f"File format '{ext}' is not supported. Allowed: {', '.join(ALLOWED_VIDEO_EXTENSIONS)}")

    # 2. Size check
    if size_bytes == 0:
        size_bytes = os.path.getsize(file_path)
    max_bytes = settings.max_video_size_mb * 1024 * 1024
    if size_bytes > max_bytes:
        raise VideoTooLargeError(settings.max_video_size_mb)

    # 3. MIME type check (don't trust Content-Type alone)
    if content_type and content_type not in ALLOWED_VIDEO_MIMETYPES:
        # Do a secondary check via magic bytes before rejecting
        try:
            with open(file_path, "rb") as f:
                header = f.read(64)
            if not _check_magic(header):
                raise InvalidVideoError(f"MIME type '{content_type}' is not a supported video format.")
        except OSError:
            pass

    # 4. ffprobe metadata validation
    try:
        info = get_video_info(file_path)
    except Exception as e:
        raise InvalidVideoError(f"Could not read media metadata: {e}")

    if not info.get("has_video"):
        raise InvalidVideoError("File does not contain a video stream.")

    # 5. Duration check
    duration = info.get("duration", 0)
    if duration <= 0:
        raise InvalidVideoError("Video has zero or unknown duration.")
    if duration > settings.max_video_duration_seconds:
        raise VideoTooLongError(settings.max_video_duration_seconds)

    return {
        **info,
        "size_bytes": size_bytes,
        "extension": ext,
    }

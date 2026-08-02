"""
YouTube / URL video ingestion service using native yt-dlp Python API.
"""
from __future__ import annotations
import os
from pathlib import Path
from typing import Optional, Dict, Any
import yt_dlp

from app.core.config import get_settings
from app.core.exceptions import VideoDownloadFailedError
from app.core.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


def get_video_metadata(url: str) -> Dict[str, Any]:
    """Return clean video metadata dict from URL using native yt-dlp."""
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'skip_download': True,
        'extract_flat': False,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            if not info:
                raise VideoDownloadFailedError("Could not fetch video information.")

            return {
                "title": info.get("title", ""),
                "duration": float(info.get("duration") or 0),
                "thumbnail": info.get("thumbnail") or (info.get("thumbnails") or [{}])[-1].get("url", ""),
                "uploader": info.get("uploader", ""),
                "view_count": info.get("view_count"),
                "description": (info.get("description") or "")[:500],
                "id": info.get("id", ""),
                "extractor": info.get("extractor_key", ""),
                "subtitles": info.get("subtitles") or info.get("automatic_captions") or {},
            }
    except yt_dlp.utils.DownloadError as e:
        stderr = str(e).lower()
        if "private video" in stderr or "sign in" in stderr:
            raise VideoDownloadFailedError("This video is private or requires authentication.")
        if "not available" in stderr or "unavailable" in stderr:
            raise VideoDownloadFailedError("This video is not available.")
        if "geo" in stderr or "region" in stderr or "restricted" in stderr:
            raise VideoDownloadFailedError("This video is not available in this region.")
        raise VideoDownloadFailedError(f"Could not fetch video info: {str(e)[:200]}")
    except Exception as e:
        raise VideoDownloadFailedError(f"Error parsing video metadata: {str(e)}")


def download_video(url: str, output_path: str) -> str:
    """
    Download video using native yt-dlp library.
    output_path should be the desired base path (without extension).
    Returns the actual downloaded file path.
    """
    output_tmpl = f"{output_path}.%(ext)s"

    ydl_opts = {
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        'outtmpl': output_tmpl,
        'merge_output_format': 'mp4',
        'quiet': True,
        'no_warnings': True,
        'retries': 3,
        'fragment_retries': 3,
        'socket_timeout': 30,
        'extractor_args': {
            'youtube': {
                'player_client': ['android', 'web']
            }
        }
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)

            # Check standard target .mp4 path
            mp4_path = f"{output_path}.mp4"
            if os.path.exists(mp4_path):
                return mp4_path

            # Check path returned by ydl
            if os.path.exists(filename):
                return filename

            # Fallback search in parent directory
            parent = Path(output_path).parent
            base = Path(output_path).name
            for f in os.listdir(parent):
                if f.startswith(base) and not f.endswith(".part"):
                    return str(parent / f)

            raise VideoDownloadFailedError("Downloaded file could not be located.")

    except yt_dlp.utils.DownloadError as e:
        stderr = str(e).lower()
        if "private" in stderr or "sign in" in stderr:
            raise VideoDownloadFailedError("This video is private or requires authentication.")
        if "unavailable" in stderr or "not available" in stderr:
            raise VideoDownloadFailedError("This video is not available.")
        raise VideoDownloadFailedError(f"Download failed: {str(e)[:300]}")
    except Exception as e:
        raise VideoDownloadFailedError(f"Video download failed: {str(e)}")
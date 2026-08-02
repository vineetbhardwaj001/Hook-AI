"""
Storage Service — abstracts local and S3 storage
"""
from __future__ import annotations
import os
import shutil
import uuid
from pathlib import Path
from typing import Optional
from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


def _analysis_dir(analysis_id: str, sub: str = "") -> Path:
    base = Path(settings.storage_local_base) / "analyses" / analysis_id
    if sub:
        base = base / sub
    base.mkdir(parents=True, exist_ok=True)
    return base


def save_uploaded_file(analysis_id: str, file_bytes: bytes, extension: str) -> str:
    """Save an uploaded video file. Returns relative storage path."""
    dest_dir = _analysis_dir(analysis_id, "source")
    filename = f"source{extension}"
    dest = dest_dir / filename
    dest.write_bytes(file_bytes)
    logger.info(f"Saved upload for analysis {analysis_id} -> {dest}")
    return str(dest)


def get_analysis_path(analysis_id: str, sub: str, filename: str) -> Path:
    """Return a Path inside the analysis directory for a given sub-folder."""
    return _analysis_dir(analysis_id, sub) / filename


def get_public_url(path: str) -> str:
    """Return a public URL or a /storage/ path for local files."""
    # In development, serve storage files via /storage route
    rel = Path(path).as_posix()
    # Strip leading storage prefix
    if rel.startswith("storage/"):
        rel = rel[len("storage/"):]
    return f"/storage/{rel}"


def cleanup_analysis(analysis_id: str) -> None:
    """Remove all files for an analysis."""
    target = Path(settings.storage_local_base) / "analyses" / analysis_id
    if target.exists():
        shutil.rmtree(target, ignore_errors=True)
        logger.info(f"Cleaned up storage for analysis {analysis_id}")


def save_frame(analysis_id: str, frame_data: bytes, frame_id: str) -> str:
    """Save an extracted frame image. Returns storage path."""
    dest_dir = _analysis_dir(analysis_id, "frames")
    dest = dest_dir / f"{frame_id}.jpg"
    dest.write_bytes(frame_data)
    return str(dest)


def save_audio(analysis_id: str, audio_path_src: str) -> str:
    """Move/copy extracted audio to analysis folder. Returns new path."""
    dest_dir = _analysis_dir(analysis_id, "audio")
    dest = dest_dir / "audio.wav"
    shutil.copy2(audio_path_src, dest)
    return str(dest)


def save_report(analysis_id: str, data: bytes, filename: str) -> str:
    """Save a report file. Returns storage path."""
    dest_dir = _analysis_dir(analysis_id, "reports")
    dest = dest_dir / filename
    dest.write_bytes(data)
    return str(dest)

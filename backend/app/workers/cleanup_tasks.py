"""Cleanup Celery tasks."""
from __future__ import annotations
import os
import shutil
from datetime import datetime, timezone, timedelta
from pathlib import Path
from app.workers.celery_app import celery_app
from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


@celery_app.task(name="app.workers.cleanup_tasks.cleanup_stale_jobs")
def cleanup_stale_jobs():
    """Remove temp files for stale / old analyses."""
    retention = timedelta(hours=settings.temp_file_retention_hours)
    cutoff = datetime.now(timezone.utc) - retention
    base = Path(settings.storage_local_base) / "analyses"
    if not base.exists():
        return

    removed = 0
    for item in base.iterdir():
        if not item.is_dir():
            continue
        mtime = datetime.fromtimestamp(item.stat().st_mtime, tz=timezone.utc)
        if mtime < cutoff:
            shutil.rmtree(item, ignore_errors=True)
            removed += 1

    logger.info(f"Cleanup: removed {removed} stale analysis directories.")
    return {"removed": removed}

"""Celery app setup — degrades gracefully if Celery is not installed."""
from __future__ import annotations
from app.core.config import get_settings

settings = get_settings()

try:
    from celery import Celery
    celery_app = Celery(
        "hook_ai",
        broker=settings.celery_broker_url,
        backend=settings.celery_result_backend,
        include=["app.workers.analysis_tasks", "app.workers.cleanup_tasks"],
    )

    celery_app.conf.update(
        task_serializer="json",
        accept_content=["json"],
        result_serializer="json",
        timezone="UTC",
        enable_utc=True,
        task_track_started=True,
        task_acks_late=True,
        worker_prefetch_multiplier=1,
    )
except ImportError:
    # Dummy fallback if celery is missing
    class DummyTask:
        def apply_async(self, *args, **kwargs):
            raise RuntimeError("Celery is not installed")

    class DummyCelery:
        def task(self, *args, **kwargs):
            def decorator(fn):
                fn.apply_async = lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("Celery is not installed"))
                return fn
            return decorator

    celery_app = DummyCelery()

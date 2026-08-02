"""
FastAPI application entry point (100% Redis-Free / MongoDB Version).
"""
from __future__ import annotations
import asyncio
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.core.exceptions import HookAIException

configure_logging()
logger = get_logger(__name__)
settings = get_settings()


# ── Helper to ensure CORS on error responses ──────────────────────────────────

def add_cors_headers(request: Request, response: JSONResponse) -> JSONResponse:
    """Ensure error responses contain CORS headers."""
    origin = request.headers.get("origin")
    if origin and (origin in settings.cors_origins or "*" in settings.cors_origins):
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Credentials"] = "true"
        response.headers["Access-Control-Allow-Methods"] = "*"
        response.headers["Access-Control-Allow-Headers"] = "*"
    return response


# ── Lifespan ──────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown."""
    logger.info(f"Hook AI Backend starting | env={settings.app_env}")

    # Ensure storage directories exist
    Path(settings.storage_local_base).mkdir(parents=True, exist_ok=True)
    (Path(settings.storage_local_base) / "analyses").mkdir(parents=True, exist_ok=True)

    # Initialize MongoDB (Motor)
    try:
        from app.db.mongo import init_mongo, close_mongo
        await init_mongo()
    except Exception as e:
        logger.warning(f"MongoDB init notice: {e}")

    # Warmup lightweight AI models
    try:
        from app.ai.model_manager import get_model_manager
        mm = get_model_manager()
        logger.info(f"ModelManager ready | device={mm.device}")
    except Exception as e:
        logger.warning(f"ModelManager warmup notice: {e}")

    logger.info("Hook AI Backend ready.")
    yield
    try:
        from app.db.mongo import close_mongo
        await close_mongo()
    except Exception:
        pass
    logger.info("Hook AI Backend shutting down.")


# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Hook AI Backend",
    description="AI-powered video intelligence API",
    version="2.0.0",
    docs_url="/docs" if settings.is_development else None,
    redoc_url="/redoc" if settings.is_development else None,
    lifespan=lifespan,
)


# ── CORS Middleware ───────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Exception Handlers ────────────────────────────────────────────────────────

@app.exception_handler(HookAIException)
async def hook_ai_exception_handler(request: Request, exc: HookAIException):
    res = JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": exc.code, "message": exc.message}},
    )
    return add_cors_headers(request, res)

@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    res = JSONResponse(
        status_code=404,
        content={"error": {"code": "NOT_FOUND", "message": "Resource not found."}},
    )
    return add_cors_headers(request, res)

@app.exception_handler(Exception)
async def internal_error_handler(request: Request, exc: Exception):
    logger.error(f"Internal error on {request.url}: {exc}", exc_info=True)
    res = JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "INTERNAL_ERROR",
                "message": str(exc) if settings.is_development else "An unexpected error occurred."
            }
        },
    )
    return add_cors_headers(request, res)


# ── Routers ───────────────────────────────────────────────────────────────────

from app.api.v1 import api_router, ws_router

app.include_router(api_router)
app.include_router(ws_router)

# Legacy /api compatibility mount
from fastapi import APIRouter
legacy = APIRouter(prefix="/api")

from app.api.v1 import auth, analyses, dashboard, profile, plans, websocket
legacy.include_router(auth.router)
legacy.include_router(analyses.router)
legacy.include_router(dashboard.router)
legacy.include_router(profile.router)
legacy.include_router(plans.router)

app.include_router(legacy)


# ── Static Storage Files ──────────────────────────────────────────────────────

storage_path = Path(settings.storage_local_base)
if not storage_path.exists():
    storage_path.mkdir(parents=True)

app.mount(
    "/storage",
    StaticFiles(directory=str(storage_path)),
    name="storage",
)


# ── Health Check ──────────────────────────────────────────────────────────────

@app.get("/health", tags=["Health"])
async def health():
    return {"status": "ok", "version": "2.0.0", "env": settings.app_env}

@app.get("/api/health", tags=["Health"])
async def api_health():
    return {"status": "ok", "version": "2.0.0"}


# ── Progress Polling Endpoint (MongoDB direct read) ───────────────────────────

@app.get("/api/analyses/{analysis_id}/progress", tags=["Progress"])
async def get_progress(analysis_id: str):
    """Fetch live progress state directly from MongoDB (No Redis)."""
    try:
        from app.db.mongo import get_mongo_db
        from bson import ObjectId, errors
        db = get_mongo_db()

        try:
            query = {"$or": [{"_id": ObjectId(analysis_id)}, {"_id": analysis_id}, {"id": analysis_id}]}
        except errors.InvalidId:
            query = {"$or": [{"_id": analysis_id}, {"id": analysis_id}]}

        doc = await db.analyses.find_one(query, {"progress": 1, "stage": 1, "status": 1, "message": 1})
        if doc:
            return JSONResponse(content={
                "analysis_id": analysis_id,
                "status": doc.get("status", "queued"),
                "stage": doc.get("stage", "queued"),
                "progress": doc.get("progress", 0),
                "message": doc.get("message", "Processing video...")
            })
    except Exception as e:
        logger.warning(f"Progress query notice: {e}")

    return JSONResponse(content={
        "analysis_id": analysis_id,
        "status": "queued",
        "stage": "queued",
        "progress": 0,
        "message": "Initializing analysis..."
    })


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=settings.is_development,
        log_level="debug" if settings.is_development else "info",
    )
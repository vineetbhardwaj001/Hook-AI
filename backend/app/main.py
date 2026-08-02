"""
FastAPI application entry point (100% Redis-Free / MongoDB Version)
With custom animated landing template for root URL (`/`).
"""
from __future__ import annotations
import asyncio
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse
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
    docs_url="/docs" if settings.is_development else "/docs",  # Kept accessible for easy API testing
    redoc_url="/redoc" if settings.is_development else "/redoc",
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


# ── HTML Landing Template (Root `/` Route) ───────────────────────────────────

LANDING_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Hook AI — Video Intelligence API</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;600;700;800&display=swap" rel="stylesheet">
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
            font-family: 'Plus Jakarta Sans', -apple-system, sans-serif;
        }

        body {
            background-color: #080c14;
            color: #f3f4f6;
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            overflow-x: hidden;
            position: relative;
        }

        /* Ambient Glow Effects */
        .glow-1 {
            position: absolute;
            width: 450px;
            height: 450px;
            background: radial-gradient(circle, rgba(99, 102, 241, 0.25) 0%, rgba(0,0,0,0) 70%);
            top: -100px;
            left: -100px;
            border-radius: 50%;
            z-index: 0;
            animation: floatGlow 12s infinite alternate ease-in-out;
        }

        .glow-2 {
            position: absolute;
            width: 500px;
            height: 500px;
            background: radial-gradient(circle, rgba(168, 85, 247, 0.2) 0%, rgba(0,0,0,0) 70%);
            bottom: -150px;
            right: -100px;
            border-radius: 50%;
            z-index: 0;
            animation: floatGlow 15s infinite alternate-reverse ease-in-out;
        }

        @keyframes floatGlow {
            0% { transform: translate(0, 0) scale(1); }
            100% { transform: translate(40px, 40px) scale(1.1); }
        }

        /* Card Container */
        .container {
            position: relative;
            z-index: 10;
            max-width: 650px;
            width: 90%;
            padding: 40px;
            background: rgba(15, 23, 42, 0.75);
            backdrop-filter: blur(16px);
            -webkit-backdrop-filter: blur(16px);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 24px;
            box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5), 0 0 30px rgba(99, 102, 241, 0.15);
            text-align: center;
            animation: fadeInUp 0.8s cubic-bezier(0.16, 1, 0.3, 1) forwards;
        }

        @keyframes fadeInUp {
            from {
                opacity: 0;
                transform: translateY(30px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }

        /* Badge */
        .badge {
            display: inline-flex;
            align-items: center;
            gap: 8px;
            padding: 6px 16px;
            border-radius: 9999px;
            background: rgba(34, 197, 94, 0.1);
            border: 1px solid rgba(34, 197, 94, 0.25);
            color: #4ade80;
            font-size: 0.85rem;
            font-weight: 600;
            margin-bottom: 24px;
        }

        .dot {
            width: 8px;
            height: 8px;
            background-color: #22c55e;
            border-radius: 50%;
            box-shadow: 0 0 10px #22c55e;
            animation: pulse 2s infinite;
        }

        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.4; }
        }

        /* Titles */
        .title {
            font-size: 3rem;
            font-weight: 800;
            letter-spacing: -0.02em;
            background: linear-gradient(135deg, #6366f1 0%, #a855f7 50%, #ec4899 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 12px;
            animation: textShimmer 4s ease-in-out infinite alternate;
        }

        .subtitle {
            font-size: 1.1rem;
            color: #94a3b8;
            margin-bottom: 32px;
            line-height: 1.6;
        }

        /* Developer Card Section */
        .dev-card {
            background: rgba(30, 41, 59, 0.6);
            border: 1px solid rgba(255, 255, 255, 0.08);
            border-radius: 16px;
            padding: 20px;
            margin-bottom: 32px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 16px;
            animation: slideIn 1s ease-out forwards;
            animation-delay: 0.3s;
            opacity: 0;
        }

        @keyframes slideIn {
            from {
                opacity: 0;
                transform: translateY(15px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }

        .dev-info {
            text-align: left;
        }

        .dev-label {
            font-size: 0.75rem;
            text-transform: uppercase;
            letter-spacing: 0.1em;
            color: #818cf8;
            font-weight: 700;
        }

        .dev-name {
            font-size: 1.15rem;
            font-weight: 700;
            color: #f8fafc;
        }

        /* Buttons */
        .btn-group {
            display: flex;
            gap: 12px;
            justify-content: center;
            flex-wrap: wrap;
        }

        .btn {
            display: inline-flex;
            align-items: center;
            gap: 8px;
            padding: 12px 24px;
            border-radius: 12px;
            font-weight: 600;
            font-size: 0.95rem;
            text-decoration: none;
            transition: all 0.2s ease;
        }

        .btn-primary {
            background: linear-gradient(135deg, #6366f1, #8b5cf6);
            color: #ffffff;
            box-shadow: 0 4px 14px rgba(99, 102, 241, 0.4);
        }

        .btn-primary:hover {
            transform: translateY(-2px);
            box-shadow: 0 6px 20px rgba(99, 102, 241, 0.6);
        }

        .btn-github {
            background: #1e293b;
            color: #f8fafc;
            border: 1px solid rgba(255, 255, 255, 0.15);
        }

        .btn-github:hover {
            background: #334155;
            transform: translateY(-2px);
            border-color: rgba(255, 255, 255, 0.3);
        }

        .btn-secondary {
            background: transparent;
            color: #cbd5e1;
            border: 1px solid rgba(255, 255, 255, 0.1);
        }

        .btn-secondary:hover {
            background: rgba(255, 255, 255, 0.05);
            color: #ffffff;
        }

        /* Footer */
        .footer-text {
            margin-top: 28px;
            font-size: 0.8rem;
            color: #64748b;
        }
    </style>
</head>
<body>
    <div class="glow-1"></div>
    <div class="glow-2"></div>

    <div class="container">
        <div class="badge">
            <span class="dot"></span>
            <span>API Status: Operational (v2.0.0)</span>
        </div>

        <h1 class="title">🎬 HOOK AI</h1>
        <p class="subtitle">AI-Powered Video Intelligence & Retention Analytics Engine</p>

        <!-- Animated GitHub / Developer Banner -->
        <div class="dev-card">
            <div class="dev-info">
                <span class="dev-label">Engineered & Managed By</span>
                <div class="dev-name">Vineet Bhardwaj</div>
            </div>
            <a href="https://github.com/vineetbhardwaj001" target="_blank" rel="noopener noreferrer" class="btn btn-github">
                <svg width="18" height="18" fill="currentColor" viewBox="0 0 24 24"><path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.33-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.595-5.475 5.895.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0024 12c0-6.63-5.37-12-12-12z"/></svg>
                GitHub Profile
            </a>
        </div>

        <!-- Action Links -->
        <div class="btn-group">
            <a href="https://new-hook.vercel.app" target="_blank" rel="noopener noreferrer" class="btn btn-primary">
                Launch Web App
            </a>
            <a href="/docs" class="btn btn-secondary">
                Swagger API Docs
            </a>
            <a href="https://github.com/vineetbhardwaj001/Hook-AI" target="_blank" rel="noopener noreferrer" class="btn btn-github">
                Source Code
            </a>
        </div>

        <p class="footer-text">Powered by FastAPI • Motor MongoDB • HuggingFace Transformers</p>
    </div>
</body>
</html>
"""


# ── Root Route (Renders Animated Landing Page) ──────────────────────────────

@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def root():
    """Serves the animated Hook AI landing page with GitHub developer banner."""
    return HTMLResponse(content=LANDING_HTML)


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
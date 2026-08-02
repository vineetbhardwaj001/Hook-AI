from fastapi import APIRouter
from app.api.v1 import auth, analyses, dashboard, profile, plans, websocket

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router)
api_router.include_router(analyses.router)
api_router.include_router(dashboard.router)
api_router.include_router(profile.router)
api_router.include_router(plans.router)

# WebSocket (no prefix override)
ws_router = APIRouter()
ws_router.include_router(websocket.router)

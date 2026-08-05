"""Plans and usage API routes — Async MongoDB (Motor) implementation."""
from __future__ import annotations
from typing import Dict, Any
from fastapi import APIRouter, Depends

from app.api.v1.deps import get_current_user
from app.db.mongo import get_mongo_db

router = APIRouter(prefix="/plans", tags=["Plans"])


PLANS_CONFIG = [
    {
        "id": "free",
        "name": "free",
        "display_name": "Free",
        "monthly_credits": 10,
        "max_video_duration_seconds": 600,
        "max_upload_size_mb": 100,
        "price_monthly": 0.0,
        "features": ["10 analyses/month", "Basic hook detection", "CTA analysis", "XLSX export"],
    },
    {
        "id": "pro",
        "name": "pro",
        "display_name": "Pro",
        "monthly_credits": 100,
        "max_video_duration_seconds": 1800,
        "max_upload_size_mb": 300,
        "price_monthly": 29.0,
        "features": ["100 analyses/month", "Full AI analysis", "Script generation", "Vision analysis", "Priority queue"],
    },
    {
        "id": "business",
        "name": "business",
        "display_name": "Business",
        "monthly_credits": 500,
        "max_video_duration_seconds": 3600,
        "max_upload_size_mb": 500,
        "price_monthly": 99.0,
        "features": ["500 analyses/month", "Everything in Pro", "API access", "Team members", "Custom models"],
    },
]


@router.get("")
async def list_plans() -> Dict[str, Any]:
    """Return configured pricing tiers."""
    return {"plans": PLANS_CONFIG}


@router.get("/usage")
async def get_usage(
    current_user: dict = Depends(get_current_user),
) -> Dict[str, Any]:
    from app.core.security import is_vip_unlimited
    if is_vip_unlimited(current_user.get("email")):
        return {
            "plan": "unlimited_pro",
            "credits": {
                "total": 999999,
                "used": 0,
                "remaining": 999999,
            },
            "limits": {
                "max_video_duration": 86400,
                "max_upload_size_mb": 5000,
            },
            "is_unlimited": True,
        }

    db = get_mongo_db()
    uid = str(current_user.get("_id") or current_user.get("id") or current_user.get("user_id"))

    # Query active subscription from MongoDB subscriptions collection
    sub = await db.subscriptions.find_one(
        {"user_id": uid, "is_active": True},
        sort=[("created_at", -1)]
    )

    if sub:
        plan_id = sub.get("plan_id", "free")
        plan_cfg = next((p for p in PLANS_CONFIG if p["id"] == plan_id), PLANS_CONFIG[0])
        plan_name = plan_cfg["name"]
        total = sub.get("monthly_credits", plan_cfg["monthly_credits"])
        used = sub.get("credits_used", 0)
        remaining = sub.get("credits_remaining", max(0, total - used))
        max_dur = plan_cfg["max_video_duration_seconds"]
        max_size = plan_cfg["max_upload_size_mb"]
    else:
        # Fallback to user document embedded plan settings
        user_plan = current_user.get("plan", "free")
        plan_cfg = next((p for p in PLANS_CONFIG if p["id"] == user_plan), PLANS_CONFIG[0])
        plan_name = plan_cfg["name"]
        total = plan_cfg["monthly_credits"]
        used = current_user.get("credits_used", 0)
        remaining = current_user.get("credits_remaining", max(0, total - used))
        max_dur = plan_cfg["max_video_duration_seconds"]
        max_size = plan_cfg["max_upload_size_mb"]

    return {
        "plan": plan_name,
        "credits": {
            "total": total,
            "used": used,
            "remaining": remaining,
        },
        "limits": {
            "max_video_duration": max_dur,
            "max_upload_size_mb": max_size,
        },
    }
"""Plans and usage API routes."""
from __future__ import annotations
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.api.v1.deps import get_current_user
from app.db.session import get_db
from app.models.user import User, Plan, Subscription

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
async def list_plans():
    return {"plans": PLANS_CONFIG}


@router.get("/usage")
async def get_usage(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    sub_q = (await db.execute(
        select(Subscription, Plan)
        .join(Plan, Plan.id == Subscription.plan_id)
        .where(Subscription.user_id == current_user.id, Subscription.is_active == True)
        .order_by(Subscription.created_at.desc())
    )).first()

    if sub_q:
        sub, plan = sub_q
        plan_name = plan.name
        total = plan.monthly_credits
        used = sub.credits_used
        remaining = sub.credits_remaining
        max_dur = plan.max_video_duration_seconds
        max_size = plan.max_upload_size_mb
    else:
        plan_name = "free"
        total, used, remaining = 10, 0, 10
        max_dur, max_size = 600, 100

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

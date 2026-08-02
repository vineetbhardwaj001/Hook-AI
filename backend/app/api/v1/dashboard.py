"""Dashboard API route — Async MongoDB (Motor) implementation."""
from __future__ import annotations
from datetime import datetime
from typing import Dict, Any, List
from fastapi import APIRouter, Depends

from app.api.v1.deps import get_current_user
from app.db.mongo import get_mongo_db

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("")
async def get_dashboard(current_user: dict = Depends(get_current_user)) -> Dict[str, Any]:
    """Return dashboard analytics summary and recent video analyses for the current user."""
    db = get_mongo_db()
    uid = str(current_user.get("_id") or current_user.get("id") or current_user.get("user_id"))

    # ── 1. AGGREGATE DASHBOARD STATS ──────────────────────────────────────────
    pipeline = [
        {"$match": {"user_id": uid}},
        {
            "$group": {
                "_id": None,
                "total_videos": {"$sum": 1},
                "scripts_generated": {
                    "$sum": {
                        "$cond": [
                            {
                                "$and": [
                                    {"$ne": ["$generated_script", None]},
                                    {"$ne": ["$generated_script", {}]},
                                ]
                            },
                            1,
                            0,
                        ]
                    }
                },
                "total_hooks": {
                    "$sum": {
                        "$cond": [
                            {"$isArray": "$hooks.hooks"},
                            {"$size": "$hooks.hooks"},
                            0,
                        ]
                    }
                },
                "avg_hook": {
                    "$avg": {
                        "$ifNull": ["$scores.hook", "$hooks.hook_score"]
                    }
                },
            }
        },
    ]

    stats_result = await db.analyses.aggregate(pipeline).to_list(length=1)

    if stats_result:
        stat_doc = stats_result[0]
        total_videos = stat_doc.get("total_videos", 0)
        scripts_generated = stat_doc.get("scripts_generated", 0)
        total_hooks = stat_doc.get("total_hooks", 0)
        avg_hook = stat_doc.get("avg_hook") or 0.0
    else:
        total_videos = 0
        scripts_generated = 0
        total_hooks = 0
        avg_hook = 0.0

    # ── 2. RECENT ANALYSES ───────────────────────────────────────────────────
    cursor = db.analyses.find({"user_id": uid}).sort("created_at", -1).limit(5)
    recent_rows = await cursor.to_list(length=5)

    recent_analyses: List[Dict[str, Any]] = []
    for a in recent_rows:
        analysis_id = str(a.get("id") or a.get("_id"))
        
        # Extract nested asset / video info safely
        asset = a.get("asset") or a.get("video") or {}
        video_title = asset.get("title") or "Untitled"
        video_source = asset.get("source") or "upload"

        # Extract nested scores
        scores = a.get("scores") or a.get("score_summary") or {}
        overall_score = scores.get("overall") or scores.get("overall_score")
        rating = scores.get("rating")

        # Format ISO timestamp
        created_at = a.get("created_at")
        if isinstance(created_at, datetime):
            created_at_str = created_at.isoformat()
        elif created_at:
            created_at_str = str(created_at)
        else:
            created_at_str = datetime.utcnow().isoformat()

        recent_analyses.append({
            "id": analysis_id,
            "status": a.get("status", "processing"),
            "analysis_type": a.get("analysis_type", "full"),
            "video_title": video_title,
            "video_source": video_source,
            "overall_score": float(overall_score) if overall_score is not None else None,
            "rating": rating,
            "created_at": created_at_str,
        })

    return {
        "stats": {
            "videos_analyzed": total_videos,
            "scripts_generated": scripts_generated,
            "hooks_detected": total_hooks,
            "average_hook_score": round(float(avg_hook), 1),
        },
        "recent_analyses": recent_analyses,
    }
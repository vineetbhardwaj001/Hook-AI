"""Dashboard API route."""
from __future__ import annotations
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from app.api.v1.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.models.analysis import Analysis, AnalysisScore, HookResult, VideoAsset, GeneratedScript

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("")
async def get_dashboard(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    uid = current_user.id

    # Stats
    total_videos = (await db.execute(select(func.count(Analysis.id)).where(Analysis.user_id == uid))).scalar_one()
    scripts_generated = (await db.execute(
        select(func.count(GeneratedScript.id))
        .join(Analysis, Analysis.id == GeneratedScript.analysis_id)
        .where(Analysis.user_id == uid)
    )).scalar_one()

    # Count hooks detected
    hooks_result = await db.execute(
        select(HookResult)
        .join(Analysis, Analysis.id == HookResult.analysis_id)
        .where(Analysis.user_id == uid)
    )
    hook_recs = hooks_result.scalars().all()
    total_hooks = sum(len(h.hooks or []) for h in hook_recs)

    # Average hook score
    avg_hook_q = await db.execute(
        select(func.avg(AnalysisScore.hook))
        .join(Analysis, Analysis.id == AnalysisScore.analysis_id)
        .where(Analysis.user_id == uid)
    )
    avg_hook = avg_hook_q.scalar_one()

    # Recent analyses
    recent_q = select(Analysis).where(Analysis.user_id == uid).order_by(Analysis.created_at.desc()).limit(5)
    recent_rows = (await db.execute(recent_q)).scalars().all()

    recent_analyses = []
    for a in recent_rows:
        asset = (await db.execute(select(VideoAsset).where(VideoAsset.analysis_id == a.id))).scalar_one_or_none()
        score = (await db.execute(select(AnalysisScore).where(AnalysisScore.analysis_id == a.id))).scalar_one_or_none()
        recent_analyses.append({
            "id": a.id,
            "status": a.status,
            "analysis_type": a.analysis_type,
            "video_title": asset.title if asset else "Untitled",
            "video_source": asset.source if asset else None,
            "overall_score": score.overall if score else None,
            "rating": score.rating if score else None,
            "created_at": a.created_at.isoformat(),
        })

    return {
        "stats": {
            "videos_analyzed": total_videos,
            "scripts_generated": scripts_generated,
            "hooks_detected": total_hooks,
            "average_hook_score": round(float(avg_hook or 0), 1),
        },
        "recent_analyses": recent_analyses,
    }

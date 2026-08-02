"""
Analyses routes — create, list, result, delete, script regeneration (MongoDB + BackgroundTasks).
"""
from __future__ import annotations
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List
from bson import ObjectId, errors as bson_errors

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, Request, Query, BackgroundTasks, status
from fastapi.responses import FileResponse
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.api.v1.deps import get_current_user, UserContext
from app.core.config import get_settings
from app.core.constants import ALLOWED_VIDEO_EXTENSIONS
from app.core.exceptions import (
    VideoTooLargeError, InvalidURLError, UnsupportedURLError
)
from app.db.mongo import get_mongo_db
from app.schemas.analysis import (
    AnalysisCreateResponse, AnalysisListResponse, AnalysisListItem,
    AnalysisResult, ScriptRegenerateRequest,
    VideoInfo, ScoreSummary, Scores, HooksResult, CTAsResult,
    ToneAnalysis, VisualAnalysis, PacingAnalysis,
    TranscriptInfo, RecommendationOut, GeneratedScriptOut, ReportInfo,
    HookDetected, CTADetected, KeyMoment, TimelineEvent, ScriptSection,
)
from app.services.storage_service import save_uploaded_file, cleanup_analysis
from app.services.url_security import validate_url, is_youtube_url
from app.core.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()
router = APIRouter(prefix="/analyses", tags=["Analyses"])


# ── Create Analysis ───────────────────────────────────────────────────────────

@router.post("", response_model=AnalysisCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_analysis(
    request: Request,
    background_tasks: BackgroundTasks,
    video: Optional[UploadFile] = File(None),
    video_url: Optional[str] = Form(None),
    videoUrl: Optional[str] = Form(None),
    analysis_type: str = Form("full"),
    language: str = Form("en"),
    category: Optional[str] = Form(None),
    notify_when_ready: bool = Form(True),
    custom_options: Optional[str] = Form(None),
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
    current_user: UserContext = Depends(get_current_user),
):
    raw_url = video_url or videoUrl

    if not video and not raw_url:
        raise HTTPException(status_code=400, detail="Provide a video file or video URL.")

    analysis_id = "an_" + str(uuid.uuid4()).replace("-", "")[:20]
    video_path = None
    source = "upload"
    video_title = None

    if video:
        ext = Path(video.filename or "video.mp4").suffix.lower()
        if ext not in ALLOWED_VIDEO_EXTENSIONS:
            raise HTTPException(status_code=400, detail=f"File format '{ext}' is not supported.")

        content = await video.read()
        size_bytes = len(content)

        if size_bytes > settings.max_video_size_mb * 1024 * 1024:
            raise VideoTooLargeError(settings.max_video_size_mb)

        video_path = save_uploaded_file(analysis_id, content, ext)
        video_title = video.filename or "Uploaded Video"
        source = "upload"

    elif raw_url:
        try:
            validated_url = validate_url(raw_url)
        except (InvalidURLError, UnsupportedURLError) as e:
            raise HTTPException(status_code=400, detail=e.message)

        source = "youtube" if is_youtube_url(raw_url) else "url"
        video_title = raw_url[:200]

    job_id = f"job_{analysis_id}"
    now = datetime.now(timezone.utc)

    analysis_doc = {
        "_id": analysis_id,
        "id": analysis_id,
        "user_id": current_user.id,
        "job_id": job_id,
        "status": "queued",
        "stage": "queued",
        "progress": 0,
        "message": "Analysis queued...",
        "analysis_type": analysis_type,
        "language": language,
        "category": category,
        "notify_when_ready": notify_when_ready,
        "created_at": now,
        "updated_at": now,
        "asset": {
            "source": source,
            "original_url": raw_url,
            "title": video_title,
            "storage_path": video_path,
        },
    }

    await db.analyses.insert_one(analysis_doc)

    # 🚀 Run background pipeline natively using FastAPI BackgroundTasks
    from app.workers.analysis_tasks import run_analysis
    background_tasks.add_task(
        run_analysis,
        analysis_id=analysis_id,
        video_path=video_path,
        video_url=raw_url,
        analysis_type=analysis_type,
        language=language,
    )

    return AnalysisCreateResponse(
        analysis_id=analysis_id,
        job_id=job_id,
        status="queued",
        message="Your video has been queued for analysis.",
    )


# ── List Analyses ─────────────────────────────────────────────────────────────

@router.get("", response_model=AnalysisListResponse)
async def list_analyses(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None),
    source: Optional[str] = Query(None),
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
    current_user: UserContext = Depends(get_current_user),
):
    filter_q = {"user_id": current_user.id}
    if status:
        filter_q["status"] = status
    if source:
        filter_q["asset.source"] = source

    total = await db.analyses.count_documents(filter_q)

    cursor = db.analyses.find(filter_q).sort("created_at", -1).skip((page - 1) * page_size).limit(page_size)
    rows = await cursor.to_list(length=page_size)

    items = []
    for a in rows:
        asset = a.get("asset") or {}
        score = a.get("score_summary") or a.get("scores") or {}
        created_at_val = a.get("created_at")
        created_at_str = created_at_val.isoformat() if isinstance(created_at_val, datetime) else str(created_at_val or "")

        items.append(AnalysisListItem(
            id=str(a.get("id") or a["_id"]),
            status=a.get("status", "queued"),
            stage=a.get("stage", "queued"),
            progress=a.get("progress", 0),
            analysis_type=a.get("analysis_type", "full"),
            video_title=asset.get("title"),
            video_source=asset.get("source"),
            video_thumbnail=asset.get("thumbnail_url"),
            overall_score=score.get("overall") or score.get("overall_score"),
            created_at=created_at_str,
        ))

    return AnalysisListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=max(1, -(-total // page_size)),
    )


# ── Get Result ────────────────────────────────────────────────────────────────

@router.get("/{analysis_id}/result", response_model=AnalysisResult)
async def get_result(
    analysis_id: str,
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
    current_user: UserContext = Depends(get_current_user),
):
    analysis = await _get_owned_analysis(db, analysis_id, current_user.id)

    if analysis.get("status") not in ("completed", "failed"):
        return AnalysisResult(
            analysis_id=analysis_id,
            status=analysis.get("status", "pending"),
        )

    if analysis.get("status") == "failed":
        return AnalysisResult(
            analysis_id=analysis_id,
            status="failed",
            error={"code": analysis.get("error_code", "ANALYSIS_FAILED"), "message": "Analysis failed."},
        )

    asset = analysis.get("asset") or {}
    transcript_rec = analysis.get("transcript") or {}
    hook_rec = analysis.get("hooks") or {}
    cta_rec = analysis.get("cta") or {}
    tone_rec = analysis.get("tone") or {}
    visual_rec = analysis.get("visual") or {}
    pacing_rec = analysis.get("pacing") or {}
    score_rec = analysis.get("scores") or {}
    summary_rec = analysis.get("score_summary") or {}
    recs = analysis.get("recommendations") or []
    script_rec = analysis.get("generated_script") or {}
    report_rec = analysis.get("report") or {}

    video_info = VideoInfo(
        title=asset.get("title"),
        thumbnail=asset.get("thumbnail_url"),
        duration=asset.get("duration"),
        width=asset.get("width"),
        height=asset.get("height"),
        source=asset.get("source"),
    ) if asset else None

    scores = Scores(
        hook=score_rec.get("hook", 0),
        cta=score_rec.get("cta", 0),
        tone=score_rec.get("tone", 0),
        visual=score_rec.get("visual", 0),
        pacing=score_rec.get("pacing", 0),
        clarity=score_rec.get("clarity", 0),
        engagement=score_rec.get("engagement", 0),
    ) if score_rec else None

    summary = ScoreSummary(
        overall_score=summary_rec.get("overall_score") or score_rec.get("overall", 0),
        rating=summary_rec.get("rating", "Unknown"),
        summary=summary_rec.get("summary"),
    ) if summary_rec or score_rec else None

    hook_data = None
    if hook_rec:
        best = hook_rec.get("best_hook") or {}
        hook_data = HooksResult(
            hook_score=round(hook_rec.get("hook_score", 0) / 10, 1),
            best_hook=HookDetected(**best) if best else None,
            hooks=[HookDetected(**h) for h in hook_rec.get("hooks", [])],
            opening_analysis=hook_rec.get("opening_analysis", {}),
            recommendations=hook_rec.get("recommendations", []),
        )

    cta_data = None
    if cta_rec:
        cta_data = CTAsResult(
            cta_score=round(cta_rec.get("cta_score", 0) / 10, 1),
            ctas=[CTADetected(**c) for c in cta_rec.get("ctas", [])],
            has_cta=cta_rec.get("has_cta", False),
            recommendations=cta_rec.get("recommendations", []),
        )

    tone_data = ToneAnalysis(
        primary_tone=tone_rec.get("primary_tone"),
        sentiment=tone_rec.get("sentiment"),
        emotions=tone_rec.get("emotions", {}),
        energy_score=tone_rec.get("energy_score", 0),
        clarity_score=tone_rec.get("clarity_score", 0),
        confidence_score=tone_rec.get("confidence_score", 0),
        observations=tone_rec.get("observations", []),
    ) if tone_rec else None

    visual_data = VisualAnalysis(
        visual_score=round(visual_rec.get("visual_score", 0) / 10, 1),
        key_moments=[KeyMoment(**m) for m in visual_rec.get("key_moments", [])[:10]],
        status=visual_rec.get("status", "unavailable"),
    ) if visual_rec else VisualAnalysis(status="unavailable")

    pacing_data = None
    if pacing_rec:
        pacing_data = PacingAnalysis(
            pacing_score=round(pacing_rec.get("pacing_score", 0) / 10, 1),
            words_per_minute=pacing_rec.get("words_per_minute"),
            silence_ratio=pacing_rec.get("silence_ratio"),
            scene_change_frequency=pacing_rec.get("scene_change_frequency"),
            timeline_events=[TimelineEvent(**e) for e in pacing_rec.get("timeline_events", [])],
            audio_signals=pacing_rec.get("audio_signals", {}),
        )

    transcript_data = TranscriptInfo(
        language=transcript_rec.get("language"),
        full_text=transcript_rec.get("full_text"),
        word_count=transcript_rec.get("word_count", 0),
        words_per_minute=transcript_rec.get("words_per_minute"),
        duration=asset.get("duration"),
        segments=transcript_rec.get("segments", []),
    ) if transcript_rec else None

    timeline = [TimelineEvent(**e) for e in pacing_rec.get("timeline_events", [])] if pacing_rec else []

    rec_list = [
        RecommendationOut(
            title=r.get("title", ""),
            description=r.get("description", ""),
            priority=r.get("priority", "medium"),
            category=r.get("category"),
            timestamp=r.get("timestamp"),
            reason=r.get("reason"),
            suggested_action=r.get("suggested_action"),
        ) for r in recs
    ]

    script_data = None
    if script_rec:
        script_data = GeneratedScriptOut(
            title=script_rec.get("title"),
            hook=script_rec.get("hook"),
            sections=[ScriptSection(**s) for s in script_rec.get("sections", [])],
            full_script=script_rec.get("full_script"),
            estimated_duration=script_rec.get("estimated_duration"),
            changes=script_rec.get("changes", []),
            platform=script_rec.get("platform"),
            tone=script_rec.get("tone"),
            version=script_rec.get("version", 1),
        )

    report_data = ReportInfo(
        xlsx_available=report_rec.get("xlsx_available", False),
        json_available=report_rec.get("json_available", False),
    ) if report_rec else None

    return AnalysisResult(
        analysis_id=analysis_id,
        status="completed",
        video=video_info,
        summary=summary,
        scores=scores,
        hooks=hook_data,
        cta=cta_data,
        tone=tone_data,
        visual=visual_data,
        pacing=pacing_data,
        transcript=transcript_data,
        timeline=timeline,
        recommendations=rec_list,
        generated_script=script_data,
        report=report_data,
    )


# ── Delete Analysis ───────────────────────────────────────────────────────────

@router.delete("/{analysis_id}")
async def delete_analysis(
    analysis_id: str,
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
    current_user: UserContext = Depends(get_current_user),
):
    analysis = await _get_owned_analysis(db, analysis_id, current_user.id)
    await db.analyses.delete_one({"_id": analysis["_id"]})
    cleanup_analysis(analysis_id)
    return {"message": "Analysis deleted."}


# ── Helper ────────────────────────────────────────────────────────────────────

async def _get_owned_analysis(db: AsyncIOMotorDatabase, analysis_id: str, user_id: str) -> dict:
    try:
        query = {
            "$or": [{"_id": ObjectId(analysis_id)}, {"_id": analysis_id}, {"id": analysis_id}],
            "user_id": user_id,
        }
    except bson_errors.InvalidId:
        query = {
            "$or": [{"_id": analysis_id}, {"id": analysis_id}],
            "user_id": user_id,
        }

    analysis = await db.analyses.find_one(query)
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found.")

    analysis["id"] = str(analysis.get("_id", analysis_id))
    return analysis
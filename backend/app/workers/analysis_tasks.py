"""
Main analysis worker — full video intelligence pipeline (Native Async / Redis-Free).
"""
from __future__ import annotations
import os
import json
import asyncio
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Any

import numpy as np

from app.core.config import get_settings
from app.core.logging import get_logger, configure_logging
from app.core.constants import STAGE_MAP
from app.db.mongo import get_mongo_db

configure_logging()
logger = get_logger(__name__)
settings = get_settings()


# ── BSON Serialization Helper ─────────────────────────────────────────────────

def sanitize_for_mongo(obj: Any) -> Any:
    """Recursively converts NumPy data types into native Python types for BSON serialization."""
    if isinstance(obj, dict):
        return {k: sanitize_for_mongo(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [sanitize_for_mongo(v) for v in obj]
    elif isinstance(obj, (np.floating, np.complexfloating)):
        return float(obj)
    elif isinstance(obj, np.integer):
        return int(obj)
    elif isinstance(obj, np.ndarray):
        return sanitize_for_mongo(obj.tolist())
    elif isinstance(obj, np.bool_):
        return bool(obj)
    return obj


# ── Progress & Status Updates (MongoDB Atlas) ─────────────────────────────────

async def push_progress(analysis_id: str, stage: str, progress: int, message: str = "", error: dict = None):
    """Update progress state directly in MongoDB Atlas on the main event loop."""
    stage_info = STAGE_MAP.get(stage, (stage, stage, progress))
    status_str = "failed" if stage == "failed" else ("completed" if stage == "completed" else "processing")
    label = stage_info[1]
    msg = message or label

    try:
        db = get_mongo_db()
        update_data = {
            "status": status_str,
            "stage": stage,
            "stage_label": label,
            "progress": progress,
            "message": msg,
            "updated_at": datetime.now(timezone.utc),
        }
        if error:
            update_data["error"] = error
            update_data["error_code"] = error.get("code")
            update_data["error_message"] = error.get("message")
        if status_str == "completed":
            update_data["completed_at"] = datetime.now(timezone.utc)

        await db.analyses.update_one(
            {"$or": [{"_id": analysis_id}, {"id": analysis_id}]},
            {"$set": sanitize_for_mongo(update_data)}
        )
    except Exception as e:
        logger.warning(f"MongoDB progress notice ({analysis_id}): {e}")

    # Terminal visual output
    bar_filled = int(progress / 5)
    bar = "█" * bar_filled + "░" * (20 - bar_filled)
    status_icon = "✅" if stage == "completed" else ("❌" if stage == "failed" else "⚙️ ")
    print(f"\r  {status_icon} [{bar}] {progress:3d}%  {label:<45}", flush=True)


# ── Main Async Pipeline Runner ────────────────────────────────────────────────

async def run_analysis(
    analysis_id: str,
    video_path: Optional[str] = None,
    video_url: Optional[str] = None,
    analysis_type: str = "full",
    language: str = "en"
) -> dict:
    """Executes the full video intelligence AI pipeline asynchronously on FastAPI's main event loop."""

    db = get_mongo_db()
    local_video_path = video_path
    audio_path = None

    print("\n" + "=" * 60, flush=True)
    print(f"  🎬 HOOK AI — ANALYSIS STARTED", flush=True)
    print(f"  ID: {analysis_id}", flush=True)
    print(f"  Type: {analysis_type.upper()} | Language: {language.upper()}", flush=True)
    print("=" * 60, flush=True)

    try:
        # ── STAGE: downloading ─────────────────────────────────────────────
        if video_url and not video_path:
            await push_progress(analysis_id, "downloading", 5, "Downloading video...")

            from app.services.url_security import validate_url
            from app.services.youtube_service import download_video

            validate_url(video_url)

            dest_dir = Path(settings.storage_local_base) / "analyses" / analysis_id / "source"
            dest_dir.mkdir(parents=True, exist_ok=True)
            dest_base = str(dest_dir / "source")

            # 🚀 RUN IN THREAD: Prevents yt-dlp from blocking the main loop
            local_video_path = await asyncio.to_thread(download_video, video_url, dest_base)

        # ── STAGE: validating ──────────────────────────────────────────────
        await push_progress(analysis_id, "validating", 10, "Validating media file...")

        from app.services.video_service import validate_video_file
        video_info = await asyncio.to_thread(validate_video_file, local_video_path, size_bytes=0)

        # ── STAGE: extracting_metadata ─────────────────────────────────────
        await push_progress(analysis_id, "extracting_metadata", 15, "Extracting video metadata...")

        duration = float(video_info["duration"])
        has_audio = bool(video_info.get("has_audio", True))

        asset_update = {
            "asset.duration": duration,
            "asset.width": video_info["width"],
            "asset.height": video_info["height"],
            "asset.fps": video_info["fps"],
            "asset.video_codec": video_info.get("video_codec"),
            "asset.audio_codec": video_info.get("audio_codec"),
            "asset.bitrate": video_info.get("bitrate"),
            "asset.size_bytes": video_info.get("size_bytes"),
            "asset.has_audio": has_audio,
        }
        if video_url:
            asset_update["asset.original_url"] = video_url

        await db.analyses.update_one(
            {"$or": [{"_id": analysis_id}, {"id": analysis_id}]},
            {"$set": sanitize_for_mongo(asset_update)}
        )

        # ── STAGE: extracting_audio ────────────────────────────────────────
        await push_progress(analysis_id, "extracting_audio", 20, "Extracting audio track...")

        transcript_text = ""
        transcript_segments = []
        transcript_language = language
        wpm = 0.0

        if has_audio:
            from app.services.ffmpeg_service import extract_audio
            audio_dir = Path(settings.storage_local_base) / "analyses" / analysis_id / "audio"
            audio_dir.mkdir(parents=True, exist_ok=True)
            audio_path = str(audio_dir / "audio.wav")
            
            await asyncio.to_thread(extract_audio, local_video_path, audio_path)

            # ── STAGE: transcribing ────────────────────────────────────────
            await push_progress(analysis_id, "transcribing", 30, "Transcribing speech with Whisper...")

            try:
                from app.ai.model_manager import get_model_manager
                mm = get_model_manager()
                whisper = mm.get_transcription_provider()
                
                result = await asyncio.to_thread(
                    whisper.transcribe, 
                    audio_path, 
                    language=language if language != "en" else None
                )

                transcript_text = result.get("full_text", "")
                transcript_segments = result.get("segments", [])
                transcript_language = result.get("language", language)
                word_count = len(transcript_text.split())
                wpm = round((word_count / duration) * 60, 1) if duration > 0 else 0.0

                await db.analyses.update_one(
                    {"$or": [{"_id": analysis_id}, {"id": analysis_id}]},
                    {"$set": sanitize_for_mongo({
                        "transcript": {
                            "language": transcript_language,
                            "full_text": transcript_text,
                            "word_count": word_count,
                            "words_per_minute": wpm,
                            "segments": transcript_segments,
                        }
                    })}
                )

            except Exception as e:
                logger.warning(f"Transcription notice for {analysis_id}: {e}")
                transcript_text = ""
                transcript_segments = []

        # ── STAGE: extracting_frames ───────────────────────────────────────
        await push_progress(analysis_id, "extracting_frames", 38, "Extracting key video frames...")

        frames_dir = str(Path(settings.storage_local_base) / "analyses" / analysis_id / "frames")
        frames = []
        visual_metrics = {"visual_score": 50.0, "frames_analyzed": 0}

        try:
            from app.services.frame_service import extract_key_frames, analyze_frames_opencv
            frames = extract_key_frames(
                video_path=local_video_path,
                output_dir=frames_dir,
                duration=duration,
            )
            frame_paths = [f["path"] for f in frames]
            visual_metrics = analyze_frames_opencv(frame_paths)
        except Exception as e:
            logger.warning(f"Frame extraction notice for {analysis_id}: {e}")

        # ── STAGE: analyzing_hooks ─────────────────────────────────────────
        await push_progress(analysis_id, "analyzing_hooks", 45, "Detecting hooks...")

        from app.services.hook_service import detect_hooks
        from app.ai.model_manager import get_model_manager
        mm = get_model_manager()

        embedder = None
        try:
            embedder = mm.get_embedding_provider()
        except Exception as e:
            logger.warning(f"Embedder notice: {e}")

        hook_result = detect_hooks(
            transcript_segments=transcript_segments,
            full_text=transcript_text,
            duration=duration,
            embedder=embedder,
        )

        await db.analyses.update_one(
            {"$or": [{"_id": analysis_id}, {"id": analysis_id}]},
            {"$set": sanitize_for_mongo({
                "hooks": {
                    "hook_score": hook_result["hook_score"],
                    "best_hook": hook_result.get("best_hook") or {},
                    "hooks": hook_result.get("hooks", []),
                    "opening_analysis": hook_result.get("opening_analysis", {}),
                    "recommendations": hook_result.get("recommendations", []),
                }
            })}
        )

        # ── STAGE: analyzing_cta ───────────────────────────────────────────
        await push_progress(analysis_id, "analyzing_cta", 52, "Analyzing CTAs...")

        from app.services.cta_service import detect_ctas

        cta_result = detect_ctas(
            transcript_segments=transcript_segments,
            duration=duration,
            embedder=embedder,
        )

        await db.analyses.update_one(
            {"$or": [{"_id": analysis_id}, {"id": analysis_id}]},
            {"$set": sanitize_for_mongo({
                "cta": {
                    "cta_score": cta_result["cta_score"],
                    "ctas": cta_result.get("ctas", []),
                    "has_cta": cta_result.get("has_cta", False),
                    "recommendations": cta_result.get("recommendations", []),
                }
            })}
        )

        # ── STAGE: analyzing_tone ──────────────────────────────────────────
        await push_progress(analysis_id, "analyzing_tone", 58, "Analyzing tone & sentiment...")

        from app.services.tone_service import analyze_tone

        tone_result = {
            "primary_tone": "Unknown", "sentiment": "Neutral", "emotions": {"neutral": 1.0},
            "energy_score": 50.0, "clarity_score": 50.0, "confidence_score": 50.0, "observations": []
        }
        try:
            emotion_provider = mm.get_emotion_provider()
            tone_result = analyze_tone(
                transcript_segments=transcript_segments,
                emotion_provider=emotion_provider,
                full_text=transcript_text,
            )
        except Exception as e:
            logger.warning(f"Tone analysis notice: {e}")

        await db.analyses.update_one(
            {"$or": [{"_id": analysis_id}, {"id": analysis_id}]},
            {"$set": sanitize_for_mongo({
                "tone": {
                    "primary_tone": tone_result.get("primary_tone"),
                    "sentiment": tone_result.get("sentiment"),
                    "emotions": tone_result.get("emotions", {}),
                    "energy_score": tone_result.get("energy_score", 50.0),
                    "clarity_score": tone_result.get("clarity_score", 50.0),
                    "confidence_score": tone_result.get("confidence_score", 50.0),
                    "observations": tone_result.get("observations", []),
                }
            })}
        )

        # ── STAGE: analyzing_audio ─────────────────────────────────────────
        await push_progress(analysis_id, "analyzing_audio", 63, "Analyzing audio signals...")

        audio_signals = {}
        if audio_path and os.path.exists(audio_path):
            from app.services.audio_service import analyze_audio
            try:
                audio_signals = analyze_audio(audio_path, transcript_segments, duration)
            except Exception as e:
                logger.warning(f"Audio analysis notice: {e}")
                from app.services.audio_service import _basic_audio_analysis
                audio_signals = _basic_audio_analysis(transcript_segments, duration)
        else:
            from app.services.audio_service import _basic_audio_analysis
            audio_signals = _basic_audio_analysis(transcript_segments, duration)

        # ── STAGE: analyzing_visuals ───────────────────────────────────────
        await push_progress(analysis_id, "analyzing_visuals", 70, "Analyzing visuals...")

        key_moments = []
        for frame in frames[:10]:
            key_moments.append({
                "timestamp": frame["timestamp"],
                "frame_url": frame.get("public_url", ""),
                "impact": "medium" if frame["reason"] == "scene_change" else "high" if frame["reason"] in ("opening", "hook_moment") else "low",
                "type": frame["reason"].replace("_", " "),
                "reason": f"Frame extracted at {frame['timestamp']:.1f}s ({frame['reason']})",
            })

        await db.analyses.update_one(
            {"$or": [{"_id": analysis_id}, {"id": analysis_id}]},
            {"$set": sanitize_for_mongo({
                "visual": {
                    "visual_score": visual_metrics.get("visual_score", 50.0),
                    "key_moments": key_moments,
                    "status": "completed",
                }
            })}
        )

        # ── STAGE: analyzing_pacing ────────────────────────────────────────
        await push_progress(analysis_id, "analyzing_pacing", 76, "Analyzing pacing...")

        from app.services.pacing_service import analyze_pacing

        pacing_result = analyze_pacing(
            transcript_segments=transcript_segments,
            audio_signals=audio_signals,
            visual_metrics=visual_metrics,
            duration=duration,
            hook_result=hook_result,
            cta_result=cta_result,
        )

        await db.analyses.update_one(
            {"$or": [{"_id": analysis_id}, {"id": analysis_id}]},
            {"$set": sanitize_for_mongo({
                "pacing": {
                    "pacing_score": pacing_result.get("pacing_score", 50.0),
                    "words_per_minute": pacing_result.get("words_per_minute"),
                    "silence_ratio": pacing_result.get("silence_ratio"),
                    "scene_change_frequency": pacing_result.get("scene_change_frequency"),
                    "timeline_events": pacing_result.get("timeline_events", []),
                    "audio_signals": audio_signals,
                }
            })}
        )

        # ── STAGE: calculating_scores ──────────────────────────────────────
        await push_progress(analysis_id, "calculating_scores", 82, "Calculating scores...")

        from app.services.scoring_service import compute_scores

        transcript_for_score = {
            "words_per_minute": wpm,
            "duration": duration,
        }
        scores = compute_scores(
            hook_result=hook_result,
            cta_result=cta_result,
            tone_result=tone_result,
            visual_metrics=visual_metrics,
            audio_signals=audio_signals,
            pacing_result=pacing_result,
            transcript=transcript_for_score,
        )

        summary_text = (
            f"Your video scored {float(scores['overall']):.1f}/10 overall ({scores['rating']}). "
            f"Hook strength: {float(scores['hook']):.1f}/10. CTA effectiveness: {float(scores['cta']):.1f}/10."
        )

        await db.analyses.update_one(
            {"$or": [{"_id": analysis_id}, {"id": analysis_id}]},
            {"$set": sanitize_for_mongo({
                "scores": scores,
                "score_summary": {
                    "overall_score": scores["overall"],
                    "rating": scores["rating"],
                    "summary": summary_text,
                }
            })}
        )

        # ── STAGE: generating_recommendations ─────────────────────────────
        await push_progress(analysis_id, "generating_recommendations", 87, "Generating recommendations...")

        from app.services.recommendation_service import generate_recommendations

        recommendations = generate_recommendations(
            hook_result=hook_result,
            cta_result=cta_result,
            tone_result=tone_result,
            pacing_result=pacing_result,
            scores=scores,
            transcript={"words_per_minute": wpm, "duration": duration},
        )

        await db.analyses.update_one(
            {"$or": [{"_id": analysis_id}, {"id": analysis_id}]},
            {"$set": sanitize_for_mongo({"recommendations": recommendations})}
        )

        # ── STAGE: generating_script ───────────────────────────────────────
        await push_progress(analysis_id, "generating_script", 92, "Generating improved script...")

        from app.services.script_service import generate_script

        generator = None
        try:
            generator = mm.get_generation_provider()
        except Exception:
            pass

        script_data = generate_script(
            transcript={"full_text": transcript_text, "duration": duration},
            hook_result=hook_result,
            cta_result=cta_result,
            tone_result=tone_result,
            pacing_result=pacing_result,
            recommendations=recommendations,
            scores=scores,
            generator=generator,
        )

        await db.analyses.update_one(
            {"$or": [{"_id": analysis_id}, {"id": analysis_id}]},
            {"$set": sanitize_for_mongo({"generated_script": script_data})}
        )

        # ── STAGE: creating_report ─────────────────────────────────────────
        await push_progress(analysis_id, "creating_report", 96, "Creating report...")

        from app.services.report_service import generate_xlsx_report
        from app.services.storage_service import save_report

        analysis_data_for_report = {
            "video": {"title": video_info.get("title", ""), "duration": duration, "width": video_info["width"], "height": video_info["height"], "source": "upload"},
            "summary": {"overall_score": scores["overall"], "rating": scores["rating"], "summary": summary_text},
            "scores": {k: v for k, v in scores.items() if k not in ("rating", "_internal")},
            "hooks": hook_result,
            "cta": cta_result,
            "tone": tone_result,
            "transcript": {"segments": transcript_segments, "duration": duration},
            "recommendations": recommendations,
            "generated_script": script_data,
        }

        report_doc = {"xlsx_available": False, "json_available": False, "xlsx_path": None, "json_path": None}

        try:
            xlsx_bytes = generate_xlsx_report(analysis_data_for_report)
            xlsx_path = save_report(analysis_id, xlsx_bytes, "analysis_report.xlsx")
            report_doc["xlsx_path"] = xlsx_path
            report_doc["xlsx_available"] = True
        except Exception as e:
            logger.warning(f"XLSX report notice: {e}")

        try:
            json_bytes = json.dumps(analysis_data_for_report, default=str, indent=2).encode()
            json_path = save_report(analysis_id, json_bytes, "analysis_report.json")
            report_doc["json_path"] = json_path
            report_doc["json_available"] = True
        except Exception as e:
            logger.warning(f"JSON report notice: {e}")

        await db.analyses.update_one(
            {"$or": [{"_id": analysis_id}, {"id": analysis_id}]},
            {"$set": sanitize_for_mongo({"report": report_doc})}
        )

        # ── STAGE: completed ───────────────────────────────────────────────
        await push_progress(analysis_id, "completed", 100, "Analysis complete!")

        logger.info(f"Analysis {analysis_id} completed successfully.")

        print("\n" + "=" * 60, flush=True)
        print(f"  ✅ HOOK AI — ANALYSIS COMPLETE!", flush=True)
        print(f"  ID: {analysis_id}", flush=True)
        print(f"  View results at: http://localhost:5173/results/{analysis_id}", flush=True)
        print("=" * 60 + "\n", flush=True)

        return {"analysis_id": analysis_id, "status": "completed"}

    except Exception as exc:
        error_msg = str(exc)
        error_code = getattr(exc, "code", "ANALYSIS_FAILED")
        logger.error(f"Analysis {analysis_id} FAILED: {error_msg}\n{traceback.format_exc()}")

        try:
            await push_progress(
                analysis_id, "failed", 0,
                f"Analysis failed: {error_msg[:100]}",
                error={"code": error_code, "message": "We could not complete this analysis."}
            )
        except Exception as inner:
            logger.error(f"Failed to record failure status: {inner}")

        raise exc
    finally:
        if audio_path and os.path.exists(audio_path):
            try:
                os.remove(audio_path)
            except Exception:
                pass
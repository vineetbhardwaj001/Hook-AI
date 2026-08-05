"""
Pacing Analysis Service.
Evaluates Words-Per-Minute (WPM), speech pauses, scene frequency,
and builds timestamped timeline events for creator retention insights.
"""
from __future__ import annotations
from typing import Dict, Any, List
from app.core.logging import get_logger

logger = get_logger(__name__)


def analyze_pacing(
    transcript_segments: List[Dict[str, Any]],
    audio_signals: Dict[str, Any],
    visual_metrics: Dict[str, Any],
    duration: float,
    hook_result: Dict[str, Any],
    cta_result: Dict[str, Any],
) -> Dict[str, Any]:
    """Analyze video pacing and build timestamped timeline events."""
    if not transcript_segments or duration <= 0:
        return {
            "pacing_score": 50.0,
            "words_per_minute": 0.0,
            "silence_ratio": round(float(audio_signals.get("silence_ratio", 0.2)), 4),
            "scene_change_frequency": 0.0,
            "timeline_events": [],
            "audio_signals": audio_signals,
        }

    # ── 1. Calculate Total Words & WPM ────────────────────────────────────────
    total_words = 0
    all_words = []

    for seg in transcript_segments:
        seg_text = seg.get("text", "").strip()
        if seg_text:
            words_in_seg = seg.get("words", [])
            if words_in_seg:
                all_words.extend(words_in_seg)
            else:
                total_words += len(seg_text.split())

    if all_words:
        total_words = len(all_words)

    wpm = round((total_words / (duration / 60.0)), 1) if duration > 0 else 0.0

    # ── 2. Scene Change Frequency ─────────────────────────────────────────────
    scene_freq = 0.0
    if visual_metrics.get("frames_analyzed", 0) > 0:
        scene_freq = round(float(visual_metrics.get("avg_motion", 0)) / 10.0, 1)

    # ── 3. Silence & Pause Extraction ─────────────────────────────────────────
    silence_ratio = float(audio_signals.get("silence_ratio", 0.2))
    long_pauses = audio_signals.get("long_pauses", []) or audio_signals.get("silence_gaps", [])

    # ── 4. Build Timeline Events ───────────────────────────────────────────────
    timeline_events = _build_timeline_events(
        transcript_segments=transcript_segments,
        long_pauses=long_pauses,
        duration=duration,
        hook_result=hook_result,
        cta_result=cta_result,
        wpm=wpm,
    )

    # ── 5. Pacing Score Calculation (0 - 100) ──────────────────────────────────
    pacing_score = 65.0

    # WPM Scoring (130-180 WPM is high-performing for short video retention)
    if 130 <= wpm <= 180:
        pacing_score += 25
    elif 100 <= wpm < 130 or 180 < wpm <= 210:
        pacing_score += 15
    elif 70 <= wpm < 100:
        pacing_score += 5
    else:  # Very slow (<70) or uncomfortably fast (>210)
        pacing_score -= 15

    # Silence Ratio Penalty/Reward
    if silence_ratio <= 0.15:
        pacing_score += 10
    elif 0.15 < silence_ratio <= 0.28:
        pacing_score += 5
    elif silence_ratio > 0.35:
        pacing_score -= 15

    # Dead Air / Critical Pause Penalties (Pauses >= 0.8s)
    critical_pauses = [p for p in long_pauses if p.get("duration", 0) >= 0.8]
    pacing_score -= min(20, len(critical_pauses) * 5)

    pacing_score = round(min(100.0, max(10.0, pacing_score)), 1)
    retention_info = calculate_predicted_completion(pacing_score / 10.0, duration)

    return {
        "pacing_score": pacing_score,
        "words_per_minute": wpm,
        "silence_ratio": round(silence_ratio, 4),
        "scene_change_frequency": scene_freq,
        "timeline_events": timeline_events,
        "audio_signals": audio_signals,
        "retention": retention_info,
        "estimated_retention_sec": retention_info["estimated_retention_sec"],
        "predicted_completion_rate": retention_info["predicted_completion_rate"],
    }


def calculate_predicted_completion(overall_score: float, duration: float) -> Dict[str, Any]:
    """Calculate realistic completion rate % and estimated watch time in seconds."""
    duration_val = max(5.0, float(duration or 30.0))
    score_val = max(1.0, min(10.0, float(overall_score or 6.5)))
    completion_rate = min(95.0, max(25.0, score_val * 11.0))
    est_watch_time = round((duration_val * completion_rate) / 100.0, 1)

    s1_end = min(3.0, duration_val)
    s2_end = min(5.0, duration_val)
    s3_end = min(10.0, duration_val)
    s4_end = duration_val

    segments = [
        {"time": f"0s - {int(s1_end)}s", "status": "excellent", "label": "Strong opening hook"},
        {"time": f"{int(s1_end)}s - {int(s2_end)}s", "status": "average", "label": "Slight drop"},
        {"time": f"{int(s2_end)}s - {int(s3_end)}s", "status": "drop", "label": "Biggest drop"},
        {"time": f"{int(s3_end)}s - {int(s4_end)}s", "status": "recover", "label": "Viewer attention recovers"}
    ]

    return {
        "estimated_retention_sec": est_watch_time,
        "predicted_completion_rate": int(completion_rate),
        "segments": segments,
    }


def _build_timeline_events(
    transcript_segments: List[Dict[str, Any]],
    long_pauses: List[Dict[str, Any]],
    duration: float,
    hook_result: Dict[str, Any],
    cta_result: Dict[str, Any],
    wpm: float,
) -> List[Dict[str, Any]]:
    events: List[Dict[str, Any]] = []

    # 1. Opening Strength Event (0-5s)
    hook_score = hook_result.get("hook_score", 0)
    events.append({
        "start": 0.0,
        "end": min(5.0, round(duration, 2)),
        "type": "strong_opening" if hook_score >= 70 else "weak_opening",
        "severity": "positive" if hook_score >= 70 else "warning",
        "message": (
            "Strong opening hook detected in the first 5 seconds"
            if hook_score >= 70
            else "Opening hook is weak — viewers may drop off early"
        ),
    })

    # 2. Silence / Long Pause Events
    for pause in long_pauses[:5]:
        pause_start = round(pause.get("start", 0), 2)
        pause_end = round(pause.get("end", pause_start + 1.0), 2)
        pause_dur = round(pause.get("duration", pause_end - pause_start), 2)

        if pause_dur >= 0.6:
            events.append({
                "start": pause_start,
                "end": pause_end,
                "type": "long_pause",
                "severity": "warning" if pause_dur >= 1.2 else "info",
                "message": f"Silence of {pause_dur:.1f}s detected — risks viewer drop-off",
            })

    # 3. Slow Pacing Sections (Windowed Check)
    if wpm > 0 and len(transcript_segments) >= 2:
        step = 3 if len(transcript_segments) >= 6 else 1
        for i in range(0, len(transcript_segments) - (step - 1), step):
            window = transcript_segments[i : i + step]
            win_start = window[0].get("start", 0)
            win_end = window[-1].get("end", win_start + 1)
            win_dur = win_end - win_start

            win_words = sum(
                len(s.get("words", [])) if s.get("words") else len(s.get("text", "").split())
                for s in window
            )

            if win_dur >= 4.0:
                seg_wpm = win_words / (win_dur / 60.0)
                if seg_wpm < 90:
                    events.append({
                        "start": round(win_start, 2),
                        "end": round(win_end, 2),
                        "type": "slow_section",
                        "severity": "warning",
                        "message": f"Pacing slows significantly ({seg_wpm:.0f} WPM) in this section",
                    })

    # 4. CTA Location Events
    for cta in cta_result.get("ctas", [])[:2]:
        cta_start = round(cta.get("start", 0), 2)
        cta_end = round(cta.get("end", cta_start + 4.0), 2)
        cta_type_str = str(cta.get("type", "cta")).replace("_", " ").title()

        events.append({
            "start": cta_start,
            "end": cta_end,
            "type": "cta",
            "severity": "positive",
            "message": f"CTA detected: '{cta_type_str}'",
        })

    # Sort chronologically
    events.sort(key=lambda e: e["start"])

    # Cap at 20 timeline events to prevent UI overflow
    return events[:20]
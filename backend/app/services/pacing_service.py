"""
Pacing Analysis Service.
"""
from __future__ import annotations
from typing import Dict, Any, List
from app.core.logging import get_logger

logger = get_logger(__name__)


def analyze_pacing(
    transcript_segments: List[Dict],
    audio_signals: Dict,
    visual_metrics: Dict,
    duration: float,
    hook_result: Dict,
    cta_result: Dict,
) -> Dict[str, Any]:
    """Analyze video pacing and build timeline events."""
    if not transcript_segments or duration <= 0:
        return {
            "pacing_score": 50.0,
            "words_per_minute": None,
            "silence_ratio": audio_signals.get("silence_ratio", 0.2),
            "scene_change_frequency": 0.0,
            "timeline_events": [],
            "audio_signals": audio_signals,
        }

    # Words per minute
    word_count = sum(len(s.get("text", "").split()) for s in transcript_segments)
    wpm = round((word_count / duration) * 60, 1) if duration > 0 else 0

    # Scene change frequency (per minute)
    scene_freq = 0.0
    if visual_metrics.get("frames_analyzed", 0) > 0:
        # Approximate from motion score
        scene_freq = round(float(visual_metrics.get("avg_motion", 0)) / 10, 1)

    silence_ratio = float(audio_signals.get("silence_ratio", 0.2))
    long_pauses = audio_signals.get("long_pauses", [])

    # Build timeline events
    timeline_events = _build_timeline_events(
        transcript_segments=transcript_segments,
        long_pauses=long_pauses,
        duration=duration,
        hook_result=hook_result,
        cta_result=cta_result,
        wpm=wpm,
    )

    # Pacing score (0-100)
    pacing_score = 60.0
    if 120 <= wpm <= 170:
        pacing_score += 20
    elif 90 <= wpm < 120:
        pacing_score += 10
    elif wpm < 60 or wpm > 220:
        pacing_score -= 15

    if 0.10 <= silence_ratio <= 0.25:
        pacing_score += 10
    elif silence_ratio > 0.35:
        pacing_score -= 10

    pacing_score -= min(15, len(long_pauses) * 4)
    pacing_score = round(min(100.0, max(0.0, pacing_score)), 1)

    return {
        "pacing_score": pacing_score,
        "words_per_minute": wpm,
        "silence_ratio": round(silence_ratio, 4),
        "scene_change_frequency": scene_freq,
        "timeline_events": timeline_events,
        "audio_signals": audio_signals,
    }


def _build_timeline_events(
    transcript_segments: List[Dict],
    long_pauses: List[Dict],
    duration: float,
    hook_result: Dict,
    cta_result: Dict,
    wpm: float,
) -> List[Dict]:
    events = []

    # Opening strength event
    opening_segs = [s for s in transcript_segments if s.get("start", 0) <= 5.0]
    if opening_segs:
        hook_score = hook_result.get("hook_score", 0)
        events.append({
            "start": 0,
            "end": min(5, duration),
            "type": "strong_opening" if hook_score >= 70 else "weak_opening",
            "severity": "positive" if hook_score >= 70 else "warning",
            "message": (
                "Strong opening hook detected in the first 5 seconds"
                if hook_score >= 70
                else "Opening hook is weak — viewers may drop off early"
            ),
        })

    # Long pause events
    for pause in long_pauses[:5]:
        events.append({
            "start": pause["start"],
            "end": pause["end"],
            "type": "long_pause",
            "severity": "warning" if pause["duration"] > 2.0 else "info",
            "message": f"Silence of {pause['duration']:.1f}s detected — may cause viewer drop-off",
        })

    # Slow speech section (if WPM < 80 for a segment)
    if wpm > 0:
        for i in range(0, len(transcript_segments) - 3, 3):
            window = transcript_segments[i:i+3]
            window_duration = window[-1].get("end", 0) - window[0].get("start", 0)
            window_words = sum(len(s.get("text","").split()) for s in window)
            if window_duration > 0:
                seg_wpm = (window_words / window_duration) * 60
                if seg_wpm < 80 and window_duration > 5:
                    events.append({
                        "start": window[0].get("start", 0),
                        "end": window[-1].get("end", 0),
                        "type": "slow_section",
                        "severity": "warning",
                        "message": f"Pacing slows significantly in this section ({seg_wpm:.0f} WPM)",
                    })

    # CTA location event
    for cta in cta_result.get("ctas", [])[:2]:
        events.append({
            "start": cta.get("start", 0),
            "end": cta.get("end", cta.get("start", 0) + 5),
            "type": "cta",
            "severity": "positive",
            "message": f"CTA detected: '{cta.get('type', 'cta').replace('_', ' ').title()}'",
        })

    # Sort by time
    events.sort(key=lambda e: e["start"])
    return events[:20]  # Cap at 20 events

"""
Deterministic Scoring Engine.
Scores are computed from actual analysis signals — not invented by LLMs.
"""
from __future__ import annotations
from typing import Dict, Any
from app.core.config import get_settings
from app.core.constants import score_to_rating

settings = get_settings()


def _normalize_to_10(score_0_100: float) -> float:
    """Convert 0-100 score to 0.0-10.0"""
    return round(min(10.0, max(0.0, score_0_100 / 10.0)), 1)


def compute_scores(
    hook_result: Dict,
    cta_result: Dict,
    tone_result: Dict,
    visual_metrics: Dict,
    audio_signals: Dict,
    pacing_result: Dict,
    transcript: Dict,
) -> Dict[str, Any]:
    """
    Compute all scores deterministically from analysis signals.
    Returns scores on 0.0-10.0 scale.
    """
    weights = settings.score_weights

    # ── Hook Score (0-100) ────────────────────────────────────────────────────
    hook_0_100 = float(hook_result.get("hook_score", 0))

    # ── CTA Score (0-100) ─────────────────────────────────────────────────────
    cta_0_100 = float(cta_result.get("cta_score", 0))
    if not cta_result.get("has_cta"):
        cta_0_100 = max(0, cta_0_100 - 20)  # Penalty for no CTA

    # ── Tone Score (0-100) ────────────────────────────────────────────────────
    energy = float(tone_result.get("energy_score", 50))
    clarity = float(tone_result.get("clarity_score", 50))
    confidence = float(tone_result.get("confidence_score", 50))
    tone_0_100 = round((energy * 0.35 + clarity * 0.35 + confidence * 0.30), 1)

    # ── Visual Score (0-100) ──────────────────────────────────────────────────
    visual_0_100 = float(visual_metrics.get("visual_score", 50))

    # ── Pacing Score (0-100) ──────────────────────────────────────────────────
    pacing_0_100 = _compute_pacing_score(audio_signals, transcript, pacing_result)

    # ── Clarity Score (0-100) ─────────────────────────────────────────────────
    clarity_0_100 = float(tone_result.get("clarity_score", 50))
    # Boost clarity from WPM signal
    wpm = float(transcript.get("words_per_minute") or 0)
    if 120 <= wpm <= 180:
        clarity_0_100 = min(100, clarity_0_100 + 10)
    elif wpm < 80 or wpm > 220:
        clarity_0_100 = max(0, clarity_0_100 - 10)

    # ── Engagement Score (0-100) ──────────────────────────────────────────────
    engagement_0_100 = _compute_engagement_score(
        hook_0_100, cta_0_100, tone_0_100, visual_0_100, pacing_0_100,
        audio_signals, transcript
    )

    # ── Weighted Overall Score ────────────────────────────────────────────────
    weighted_0_100 = (
        hook_0_100 * weights["hook"] +
        cta_0_100 * weights["cta"] +
        tone_0_100 * weights["tone"] +
        visual_0_100 * weights["visual"] +
        pacing_0_100 * weights["pacing"] +
        clarity_0_100 * weights["clarity"] +
        engagement_0_100 * weights["engagement"]
    )
    overall_0_100 = round(min(100.0, max(0.0, weighted_0_100)), 1)

    # Convert all to 0-10 scale
    return {
        "overall": _normalize_to_10(overall_0_100),
        "hook": _normalize_to_10(hook_0_100),
        "cta": _normalize_to_10(cta_0_100),
        "tone": _normalize_to_10(tone_0_100),
        "visual": _normalize_to_10(visual_0_100),
        "pacing": _normalize_to_10(pacing_0_100),
        "clarity": _normalize_to_10(clarity_0_100),
        "engagement": _normalize_to_10(engagement_0_100),
        "rating": score_to_rating(_normalize_to_10(overall_0_100)),
        # Internal 0-100 breakdown for explainability
        "_internal": {
            "hook": hook_0_100,
            "cta": cta_0_100,
            "tone": tone_0_100,
            "visual": visual_0_100,
            "pacing": pacing_0_100,
            "clarity": clarity_0_100,
            "engagement": engagement_0_100,
            "overall": overall_0_100,
        }
    }


def _compute_pacing_score(audio_signals: Dict, transcript: Dict, pacing_result: Dict) -> float:
    """Compute pacing score from audio and transcript signals."""
    score = 60.0

    # WPM signal
    wpm = float(transcript.get("words_per_minute") or 0)
    if 120 <= wpm <= 170:
        score += 20  # Optimal speech rate
    elif 90 <= wpm < 120:
        score += 10  # Slightly slow but OK
    elif wpm < 60:
        score -= 15  # Too slow
    elif wpm > 200:
        score -= 10  # Too fast

    # Silence ratio signal
    silence_ratio = float(audio_signals.get("silence_ratio", 0.2))
    if 0.10 <= silence_ratio <= 0.25:
        score += 10  # Natural pausing
    elif silence_ratio > 0.40:
        score -= 15  # Too many pauses
    elif silence_ratio < 0.05:
        score -= 5   # No breathing room

    # Long pauses penalty
    long_pauses = audio_signals.get("long_pauses", [])
    score -= min(20, len(long_pauses) * 5)

    return round(min(100.0, max(0.0, score)), 1)


def _compute_engagement_score(
    hook: float, cta: float, tone: float, visual: float, pacing: float,
    audio_signals: Dict, transcript: Dict,
) -> float:
    """Heuristic engagement estimate from multiple signals."""
    # Weighted sub-scores
    base = (
        hook * 0.30 +
        cta * 0.15 +
        tone * 0.15 +
        visual * 0.20 +
        pacing * 0.10
    )

    # Bonus for energy variation (keeps viewers engaged)
    energy_var = float(audio_signals.get("energy_variation", 0))
    if energy_var > 0.2:
        base = min(100, base + 5)

    # Penalty for very short or very long videos
    duration = float(transcript.get("duration") or 60)
    if duration < 30:
        base = max(0, base - 10)

    return round(min(100.0, max(0.0, base)), 1)

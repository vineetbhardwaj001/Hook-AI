"""
CTA Detection Engine — keyword + regex + semantic embedding.
"""
from __future__ import annotations
import re
from typing import List, Dict, Any, Optional
from app.core.logging import get_logger

logger = get_logger(__name__)

# ── CTA keyword/regex banks ───────────────────────────────────────────────────
CTA_RULES: Dict[str, Dict] = {
    "subscribe": {
        "patterns": [r'\b(subscribe|hit subscribe|subscribe now|subscribe button|don.t forget to subscribe)\b'],
        "strength": "strong",
    },
    "follow": {
        "patterns": [r'\b(follow me|follow us|follow for|follow this account|give us a follow)\b'],
        "strength": "strong",
    },
    "like": {
        "patterns": [r'\b(like this video|smash the like|hit like|drop a like|if you liked)\b'],
        "strength": "medium",
    },
    "comment": {
        "patterns": [r'\b(comment below|let me know in the comments|leave a comment|drop a comment)\b'],
        "strength": "medium",
    },
    "share": {
        "patterns": [r'\b(share this|share with|share it|share the video)\b'],
        "strength": "medium",
    },
    "buy": {
        "patterns": [r'\b(buy now|purchase|order now|get yours|shop now|add to cart|checkout)\b'],
        "strength": "strong",
    },
    "download": {
        "patterns": [r'\b(download|download now|get the free|grab the)\b'],
        "strength": "medium",
    },
    "register": {
        "patterns": [r'\b(sign up|register|create an account|join free|start free)\b'],
        "strength": "strong",
    },
    "link_in_bio": {
        "patterns": [r'\b(link in bio|link in description|check the description|check the link)\b'],
        "strength": "medium",
    },
    "visit": {
        "patterns": [r'\b(visit|go to|check out|head over to)\s+\w+\.(com|io|co|net|org)\b'],
        "strength": "medium",
    },
    "learn_more": {
        "patterns": [r'\b(learn more|find out more|for more info|more details|see more)\b'],
        "strength": "low",
    },
    "join": {
        "patterns": [r'\b(join us|join the community|join my|become a member)\b'],
        "strength": "strong",
    },
    "dm": {
        "patterns": [r'\b(dm me|send me a dm|direct message|message me)\b'],
        "strength": "medium",
    },
    "try": {
        "patterns": [r'\b(try it|try for free|try now|give it a try)\b'],
        "strength": "medium",
    },
    "book": {
        "patterns": [r'\b(book a call|book now|schedule a call|book your|reserve your)\b'],
        "strength": "strong",
    },
}

# Strength-to-score mapping
STRENGTH_SCORES = {"strong": 85, "medium": 65, "low": 45}

CTA_EXEMPLARS = [
    "Subscribe and hit the bell to never miss a video.",
    "Click the link in my bio to get started for free.",
    "Drop a comment below and let me know what you think.",
    "Share this with someone who needs to see it.",
    "Join my free community — link in the description.",
    "Book a free strategy call at the link below.",
    "Follow me for more tips like this.",
    "Download the free guide linked in the description.",
]


def _match_cta(text: str) -> Optional[str]:
    text_l = text.lower()
    for cta_type, rules in CTA_RULES.items():
        for pattern in rules["patterns"]:
            if re.search(pattern, text_l, re.IGNORECASE):
                return cta_type
    return None


def _score_cta(text: str, cta_type: str, position_pct: float, embedder=None) -> float:
    strength = CTA_RULES.get(cta_type, {}).get("strength", "low")
    base_score = float(STRENGTH_SCORES.get(strength, 45))

    # Ending bonus — CTAs near the end are more expected and effective
    if position_pct > 0.85:
        base_score += 10
    elif position_pct > 0.70:
        base_score += 5

    # Semantic similarity bonus
    if embedder:
        try:
            sims = embedder.batch_similarity(text, CTA_EXEMPLARS)
            avg_sim = sum(sims) / len(sims) if sims else 0.0
            base_score += avg_sim * 10
        except Exception:
            pass

    return round(min(100.0, max(0.0, base_score)), 1)


def detect_ctas(
    transcript_segments: List[Dict],
    duration: float,
    embedder=None,
) -> Dict[str, Any]:
    """Main CTA detection function."""
    if not transcript_segments or duration <= 0:
        return {
            "cta_score": 0.0,
            "ctas": [],
            "has_cta": False,
            "recommendations": ["Add a clear call-to-action — tell viewers exactly what to do next."],
        }

    detected_ctas = []

    for seg in transcript_segments:
        text = seg.get("text", "").strip()
        if len(text) < 3:
            continue
        start = seg.get("start", 0)
        end = seg.get("end", start + 1)
        position_pct = start / duration if duration > 0 else 0

        cta_type = _match_cta(text)
        if cta_type:
            score = _score_cta(text, cta_type, position_pct, embedder)
            strength = CTA_RULES.get(cta_type, {}).get("strength", "low")
            detected_ctas.append({
                "text": text,
                "start": start,
                "end": end,
                "type": cta_type,
                "strength": strength,
                "score": score,
            })

    # Deduplicate overlapping CTAs (same type within 5s)
    deduped = []
    seen: Dict[str, float] = {}
    for cta in sorted(detected_ctas, key=lambda x: x["score"], reverse=True):
        key = cta["type"]
        last_seen = seen.get(key, -10)
        if abs(cta["start"] - last_seen) > 5.0:
            deduped.append(cta)
            seen[key] = cta["start"]

    deduped.sort(key=lambda x: x["start"])
    has_cta = len(deduped) > 0

    # CTA score
    if deduped:
        top_scores = sorted([c["score"] for c in deduped], reverse=True)[:3]
        cta_score = round(sum(top_scores) / len(top_scores), 1)
        # Bonus for having end CTA
        has_end_cta = any(c["start"] / duration > 0.80 for c in deduped)
        if has_end_cta:
            cta_score = min(100.0, cta_score + 8)
    else:
        cta_score = 0.0

    recommendations = _build_cta_recommendations(deduped, duration)

    return {
        "cta_score": cta_score,
        "ctas": deduped,
        "has_cta": has_cta,
        "recommendations": recommendations,
    }


def _build_cta_recommendations(ctas: list, duration: float) -> List[str]:
    recs = []
    if not ctas:
        recs.append("Add a clear call-to-action — subscribe, follow, buy, or visit a link.")
        recs.append("Place your primary CTA in the final 20% of the video for maximum impact.")
        return recs

    end_ctas = [c for c in ctas if c["start"] / duration > 0.80] if duration > 0 else []
    mid_ctas = [c for c in ctas if 0.3 < c["start"] / duration < 0.70] if duration > 0 else []

    if not end_ctas:
        recs.append(
            "Add a strong CTA in the last 15-20 seconds of your video — viewers who watch to the end are most likely to convert."
        )
    if not mid_ctas:
        recs.append(
            "Consider adding a soft CTA around the midpoint (e.g., 'If this is helpful, subscribe for more') to capture mid-video dropoffs."
        )
    weak_ctas = [c for c in ctas if c["strength"] == "low"]
    if weak_ctas and not any(c["strength"] == "strong" for c in ctas):
        recs.append(
            "Your CTAs are passive (e.g., 'learn more'). Replace with direct action words like 'Subscribe now' or 'Click the link below'."
        )
    return recs[:3]

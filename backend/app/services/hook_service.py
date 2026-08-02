"""
Hook Detection Engine — hybrid rule + regex + embedding-based detection.
"""
from __future__ import annotations
import re
from typing import List, Dict, Any, Optional
from app.core.logging import get_logger

logger = get_logger(__name__)

# ── Hook Keyword Banks ────────────────────────────────────────────────────────
QUESTION_PATTERNS = [
    r'\b(what if|did you know|have you ever|why does|how does|can you|would you|do you know)\b',
    r'\?',
]
BOLD_CLAIM_PATTERNS = [
    r'\b(secret|truth|never told|no one talks about|hidden|proven|guaranteed|shocking|unbelievable)\b',
]
NUMBER_PATTERNS = [
    r'\b\d+\s+(ways|tips|tricks|reasons|steps|secrets|mistakes|habits|hacks|things)\b',
    r'\b(top|best)\s+\d+\b',
]
PAIN_POINT_PATTERNS = [
    r'\b(struggling|tired of|sick of|frustrated|failing|not working|problem|issue|challenge|mistake)\b',
]
RESULT_FIRST_PATTERNS = [
    r'\b(made|earned|saved|lost|gained|grew|increased|doubled|tripled|went from)\b.*\b(in|within|after|under)\b',
]
PROMISE_PATTERNS = [
    r'\b(by the end|in this video|i.ll show|you.ll learn|you.ll discover|you.ll get)\b',
]
CURIOSITY_GAP_PATTERNS = [
    r'\b(most people|everyone gets wrong|don.t want you to|they.re hiding|the real reason)\b',
]
STORY_PATTERNS = [
    r'\b(i was|it was|last year|years ago|when i|back in|my story|true story|happened to)\b',
]
CONTRARIAN_PATTERNS = [
    r'\b(stop|don.t|wrong|myth|lie|actually|contrary|opposite|forget everything)\b',
]
AUTHORITY_PATTERNS = [
    r'\b(\d+\s+years?\s+(of\s+)?experience|i.ve\s+(helped|worked|built|made)|expert|professional|specialist)\b',
]
PATTERN_INTERRUPT = [
    r'\b(wait|hold on|before you|listen|attention|important|breaking|alert)\b',
]

HOOK_EXEMPLARS = {
    "question": ["Did you know that 90% of people make this mistake?", "What if I told you this changes everything?"],
    "curiosity_gap": ["The real reason nobody tells you about this...", "Most people get this completely wrong."],
    "bold_claim": ["This secret technique tripled my views in 30 days.", "The hidden truth about YouTube growth."],
    "number": ["7 proven ways to grow your channel faster.", "Top 5 mistakes new creators make."],
    "pain_point": ["Tired of posting videos that nobody watches?", "Struggling to get views despite working hard?"],
    "result_first": ["I gained 100K subscribers in 6 months. Here's exactly how.", "From 0 to $10K/month doing this."],
    "promise": ["By the end of this video, you'll know exactly what to do.", "I'll show you the exact system I use."],
    "story": ["I was about to quit YouTube when this happened.", "Two years ago I had zero subscribers."],
    "emotional": ["This changed my life completely.", "I can't believe nobody talks about this."],
    "authority": ["After 10 years building YouTube channels, I've learned...", "I've helped 500 creators grow to 100K."],
    "contrarian": ["Stop using this strategy — it's killing your growth.", "Forget everything you know about hooks."],
    "pattern_interrupt": ["Wait — before you hit record, hear this.", "Hold on. Most creators skip this step."],
}


def _match_patterns(text: str, patterns: list) -> bool:
    text_l = text.lower()
    for p in patterns:
        if re.search(p, text_l, re.IGNORECASE):
            return True
    return False


def _detect_hook_type(text: str) -> Optional[str]:
    text_l = text.lower()
    checks = [
        ("question", QUESTION_PATTERNS),
        ("number", NUMBER_PATTERNS),
        ("pain_point", PAIN_POINT_PATTERNS),
        ("result_first", RESULT_FIRST_PATTERNS),
        ("promise", PROMISE_PATTERNS),
        ("curiosity_gap", CURIOSITY_GAP_PATTERNS),
        ("bold_claim", BOLD_CLAIM_PATTERNS),
        ("story", STORY_PATTERNS),
        ("contrarian", CONTRARIAN_PATTERNS),
        ("authority", AUTHORITY_PATTERNS),
        ("pattern_interrupt", PATTERN_INTERRUPT),
    ]
    for hook_type, patterns in checks:
        if _match_patterns(text_l, patterns):
            return hook_type
    return None


def _score_hook(text: str, hook_type: Optional[str], position_pct: float, embedder=None) -> float:
    """Score a hook on 0-100 scale."""
    score = 50.0

    # Position bonus (earlier = stronger hook potential)
    if position_pct < 0.05:     # first 5% of video
        score += 20
    elif position_pct < 0.10:   # 5-10%
        score += 10
    elif position_pct < 0.20:
        score += 5

    # Hook type bonus
    type_bonuses = {
        "question": 12,
        "number": 10,
        "curiosity_gap": 15,
        "result_first": 12,
        "bold_claim": 10,
        "pain_point": 10,
        "promise": 8,
        "story": 7,
        "contrarian": 10,
        "pattern_interrupt": 8,
        "authority": 7,
        "emotional": 6,
    }
    score += type_bonuses.get(hook_type or "", 0)

    # Length penalty for very short hooks
    words = text.split()
    if len(words) < 4:
        score -= 10
    elif len(words) > 30:
        score -= 5

    # Semantic similarity bonus with known strong hooks (if embedder available)
    if embedder and hook_type and hook_type in HOOK_EXEMPLARS:
        try:
            exemplars = HOOK_EXEMPLARS[hook_type]
            sims = embedder.batch_similarity(text, exemplars)
            avg_sim = sum(sims) / len(sims) if sims else 0.0
            score += avg_sim * 15  # up to +15
        except Exception:
            pass

    return round(min(100.0, max(0.0, score)), 1)


def detect_hooks(
    transcript_segments: List[Dict],
    full_text: str,
    duration: float,
    embedder=None,
) -> Dict[str, Any]:
    """
    Main hook detection function.
    Returns structured hook result dict.
    """
    if not transcript_segments or duration <= 0:
        return {
            "hook_score": 0.0,
            "best_hook": None,
            "hooks": [],
            "opening_analysis": {"first_3s": "", "first_5s": "", "first_10s": ""},
            "recommendations": ["Add a clear hook in the first 3 seconds of your video."],
        }

    # Build opening text windows
    first_3s = " ".join(s["text"] for s in transcript_segments if s.get("start", 0) <= 3.0)
    first_5s = " ".join(s["text"] for s in transcript_segments if s.get("start", 0) <= 5.0)
    first_10s = " ".join(s["text"] for s in transcript_segments if s.get("start", 0) <= 10.0)

    detected_hooks = []

    for seg in transcript_segments:
        text = seg.get("text", "").strip()
        if len(text) < 5:
            continue
        start = seg.get("start", 0)
        end = seg.get("end", start + 1)
        position_pct = start / duration if duration > 0 else 0

        hook_type = _detect_hook_type(text)
        if hook_type or position_pct < 0.15:  # Check first 15% of video
            score = _score_hook(text, hook_type, position_pct, embedder)
            if score >= 55:  # Only include meaningful hooks
                detected_hooks.append({
                    "text": text,
                    "start": start,
                    "end": end,
                    "type": hook_type or "general",
                    "score": score,
                    "reason": _build_reason(hook_type, score, position_pct),
                })

    # Sort by score
    detected_hooks.sort(key=lambda h: h["score"], reverse=True)

    best_hook = detected_hooks[0] if detected_hooks else None

    # Compute overall hook score
    if detected_hooks:
        top_scores = [h["score"] for h in detected_hooks[:3]]
        has_early_hook = any(h["start"] <= 5.0 for h in detected_hooks)
        has_question = any(h["type"] == "question" for h in detected_hooks)
        base = sum(top_scores) / len(top_scores)
        if has_early_hook:
            base = min(100, base + 10)
        if has_question:
            base = min(100, base + 5)
        hook_score = round(base, 1)
    else:
        hook_score = max(0.0, 20.0 + (10 if first_3s else 0))

    recommendations = _build_hook_recommendations(detected_hooks, first_3s, first_5s, duration)

    return {
        "hook_score": hook_score,
        "best_hook": best_hook,
        "hooks": detected_hooks[:10],
        "opening_analysis": {
            "first_3s": first_3s,
            "first_5s": first_5s,
            "first_10s": first_10s,
        },
        "recommendations": recommendations,
    }


def _build_reason(hook_type: Optional[str], score: float, position_pct: float) -> str:
    reasons = {
        "question": "Opens with a direct question to engage viewer curiosity",
        "curiosity_gap": "Creates information gap that keeps viewers watching",
        "bold_claim": "Makes a strong claim that establishes credibility",
        "number": "Uses specific numbers to set clear expectations",
        "pain_point": "Directly addresses viewer frustrations",
        "result_first": "Leads with the outcome to demonstrate value",
        "promise": "Clearly promises specific value to the viewer",
        "story": "Uses narrative to create emotional connection",
        "contrarian": "Challenges assumptions to create intrigue",
        "authority": "Establishes expertise and trustworthiness",
        "pattern_interrupt": "Interrupts passive viewing to demand attention",
        "emotional": "Creates strong emotional resonance",
        "general": "Contains engaging opening content",
    }
    base = reasons.get(hook_type or "general", "Engaging opening content")
    timing = "in the crucial first 3 seconds" if position_pct < 0.05 else "early in the video"
    return f"{base} ({timing})"


def _build_hook_recommendations(hooks: list, first_3s: str, first_5s: str, duration: float) -> List[str]:
    recs = []
    early_hooks = [h for h in hooks if h["start"] <= 5.0]

    if not early_hooks:
        recs.append(
            "Move your opening statement to the first 3 seconds — your current hook starts too late to retain viewers."
        )
    if not first_3s.strip():
        recs.append("Your video has no speech in the first 3 seconds. Add an immediate verbal hook.")
    if not any(h["type"] == "question" for h in hooks):
        recs.append("Consider opening with a direct question to immediately engage viewer curiosity.")
    if not any(h["type"] in ("result_first", "bold_claim") for h in hooks):
        recs.append(
            "Try leading with your strongest result or claim — viewers decide in 3 seconds whether to keep watching."
        )
    if len(hooks) == 0:
        recs.append(
            "No clear hooks detected. Start with something attention-grabbing: a surprising statistic, a bold claim, or a direct question."
        )
    return recs[:4]  # Limit to most relevant

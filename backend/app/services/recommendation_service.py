"""
Recommendation Engine — generates specific, actionable recommendations.
"""
from __future__ import annotations
from typing import List, Dict, Any


def generate_recommendations(
    hook_result: Dict,
    cta_result: Dict,
    tone_result: Dict,
    pacing_result: Dict,
    scores: Dict,
    transcript: Dict,
) -> List[Dict[str, Any]]:
    """
    Generate specific, timestamp-based, actionable recommendations.
    Never returns generic advice.
    """
    recs = []
    order = 0

    def add(title: str, description: str, priority: str, category: str,
            timestamp: float = None, reason: str = None, action: str = None):
        nonlocal order
        recs.append({
            "title": title,
            "description": description,
            "priority": priority,
            "category": category,
            "timestamp": timestamp,
            "reason": reason,
            "suggested_action": action,
            "order_index": order,
        })
        order += 1

    # ── Hook Recommendations ──────────────────────────────────────────────────
    hook_score = scores.get("hook", 0) * 10  # 0-100
    best_hook = hook_result.get("best_hook")
    hooks = hook_result.get("hooks", [])

    if hook_score < 60:
        add(
            title="Strengthen Your Opening Hook",
            description="Your hook score is below average. Viewers decide in 3 seconds whether to keep watching.",
            priority="high",
            category="hook",
            timestamp=0.0,
            reason=f"Hook score: {hook_score:.0f}/100",
            action="Start with a specific question, bold claim, or your strongest result. Example: 'In the next 60 seconds, I'll show you exactly how I...'",
        )

    if best_hook and best_hook.get("start", 0) > 5.0:
        add(
            title="Move Your Best Hook Earlier",
            description=f"Your strongest hook appears at {best_hook['start']:.1f}s — too late for most viewers.",
            priority="high",
            category="hook",
            timestamp=best_hook.get("start"),
            reason="Hooks must appear within the first 3-5 seconds to prevent drop-off",
            action=f"Move this statement to the very beginning: '{best_hook.get('text', '')[:80]}...'",
        )

    # ── CTA Recommendations ───────────────────────────────────────────────────
    cta_score = scores.get("cta", 0) * 10
    ctas = cta_result.get("ctas", [])
    has_end_cta = any(c.get("start", 0) > (transcript.get("duration", 60) * 0.80) for c in ctas)

    if not cta_result.get("has_cta"):
        add(
            title="Add a Clear Call-to-Action",
            description="No CTA detected in your video. Videos without CTAs lose potential subscribers, followers, and conversions.",
            priority="high",
            category="cta",
            timestamp=None,
            reason="Missing CTA means viewers have no clear next step",
            action="Add a specific CTA near the end: 'Subscribe now and hit the bell so you never miss a video like this.'",
        )
    elif not has_end_cta:
        duration = transcript.get("duration", 60)
        add(
            title="Add a Closing CTA",
            description="Your CTAs appear too early. Viewers who watch to the end are 3x more likely to convert.",
            priority="medium",
            category="cta",
            timestamp=duration * 0.85 if duration > 0 else None,
            reason="No CTA detected in the final 20% of the video",
            action="End the video with a direct, specific ask. Repeat your subscription/follow CTA in the final 15 seconds.",
        )

    # ── Tone/Energy Recommendations ───────────────────────────────────────────
    energy_score = float(tone_result.get("energy_score", 50))
    if energy_score < 55:
        add(
            title="Increase Your Delivery Energy",
            description=f"Your energy score is {energy_score:.0f}/100. Low-energy delivery causes viewer disengagement.",
            priority="medium",
            category="tone",
            reason="Low energy score detected from emotion analysis",
            action="Speak 10-15% faster, use more varied intonation, and start sentences with action words.",
        )

    sentiment = tone_result.get("sentiment", "Neutral")
    if sentiment == "Negative":
        add(
            title="Balance Negative Tone with Positive Resolution",
            description="Your overall sentiment skews negative. While contrast can be effective, ensure the video ends on a positive/actionable note.",
            priority="low",
            category="tone",
            reason="Dominant negative sentiment detected across transcript segments",
            action="Add a forward-looking conclusion: 'Here's exactly what you can do to fix this...'",
        )

    # ── Pacing Recommendations ────────────────────────────────────────────────
    wpm = pacing_result.get("words_per_minute", 0) or 0
    long_pauses = (pacing_result.get("audio_signals") or {}).get("long_pauses", [])

    if wpm > 0 and wpm < 100:
        add(
            title="Increase Speech Pace",
            description=f"Current pace of {wpm:.0f} WPM is too slow. Optimal for engagement is 130-170 WPM.",
            priority="medium",
            category="pacing",
            reason="Words-per-minute below optimal engagement threshold",
            action="Practice speaking 20-30% faster. Remove filler phrases and unnecessary pauses in editing.",
        )
    elif wpm > 200:
        add(
            title="Slow Down Your Delivery",
            description=f"Current pace of {wpm:.0f} WPM is too fast. Viewers can't absorb information quickly enough.",
            priority="medium",
            category="pacing",
            reason="Speech rate exceeds optimal comprehension range",
            action="Add deliberate pauses after key points. Aim for 130-170 WPM.",
        )

    if len(long_pauses) > 3:
        worst_pause = max(long_pauses, key=lambda p: p["duration"])
        add(
            title="Remove Long Silences in Editing",
            description=f"Found {len(long_pauses)} silences longer than 1.5s, including a {worst_pause['duration']:.1f}s pause at {worst_pause['start']:.1f}s.",
            priority="medium",
            category="pacing",
            timestamp=worst_pause.get("start"),
            reason="Long silences cause viewer drop-off",
            action="Cut silences longer than 1 second in post-production. Use jump cuts or B-roll to maintain momentum.",
        )

    # ── Clarity Recommendations ───────────────────────────────────────────────
    clarity_score = scores.get("clarity", 0) * 10
    if clarity_score < 60:
        add(
            title="Improve Script Clarity",
            description=f"Clarity score is {clarity_score:.0f}/100. Use shorter sentences and clearer structure.",
            priority="medium",
            category="clarity",
            reason="Low clarity score from speech density analysis",
            action="Use the rule of one: one idea per sentence, one topic per section. Avoid multi-part sentences.",
        )

    # Sort by priority
    priority_order = {"high": 0, "medium": 1, "low": 2}
    recs.sort(key=lambda r: priority_order.get(r["priority"], 3))

    return recs[:12]  # Return top 12 recommendations

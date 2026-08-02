"""
Script Generation Service.
Uses the configured text generation model (or rule-based fallback).
"""
from __future__ import annotations
from typing import Dict, Any, List, Optional
from app.core.logging import get_logger

logger = get_logger(__name__)


def generate_script(
    transcript: Dict,
    hook_result: Dict,
    cta_result: Dict,
    tone_result: Dict,
    pacing_result: Dict,
    recommendations: List[Dict],
    scores: Dict,
    platform: str = "YouTube",
    audience: str = "General audience",
    target_duration: Optional[int] = None,
    goal: str = "Engagement",
    tone: str = "Energetic",
    style: str = "Educational",
    generator=None,
) -> Dict[str, Any]:
    """
    Generate an improved script using either a local LLM or rule-based approach.
    """
    original_text = transcript.get("full_text", "")
    original_duration = transcript.get("duration", 60)
    est_duration = target_duration or int(original_duration)

    # Build structured prompt
    best_hook = hook_result.get("best_hook") or {}
    existing_hook = best_hook.get("text", "")
    hook_type = best_hook.get("type", "")

    top_cta = (cta_result.get("ctas") or [{}])[0] if cta_result.get("ctas") else {}
    existing_cta = top_cta.get("text", "")

    # High-priority recommendations as context
    high_recs = [r for r in recommendations if r.get("priority") == "high"][:3]
    rec_lines = "\n".join(f"- {r.get('title')}: {r.get('suggested_action', '')}" for r in high_recs)

    # Try LLM generation first
    if generator:
        try:
            return _generate_with_llm(
                generator=generator,
                original_text=original_text,
                existing_hook=existing_hook,
                existing_cta=existing_cta,
                platform=platform,
                audience=audience,
                tone=tone,
                goal=goal,
                recommendations=rec_lines,
                est_duration=est_duration,
            )
        except Exception as e:
            logger.warning(f"LLM script generation failed: {e}. Using rule-based fallback.")

    # Fallback: rule-based script assembly
    return _generate_rule_based(
        original_text=original_text,
        existing_hook=existing_hook,
        hook_type=hook_type,
        existing_cta=existing_cta,
        tone_result=tone_result,
        recommendations=recommendations,
        platform=platform,
        audience=audience,
        tone=tone,
        est_duration=est_duration,
    )


def _generate_with_llm(generator, original_text, existing_hook, existing_cta,
                        platform, audience, tone, goal, recommendations, est_duration) -> Dict:
    """Generate script using local LLM."""
    prompt = f"""You are an expert video script writer for {platform} creators.

Original transcript snippet:
{original_text[:800]}

Current hook: {existing_hook[:200] if existing_hook else "None detected"}
Current CTA: {existing_cta[:200] if existing_cta else "None detected"}
Target platform: {platform}
Target audience: {audience}
Desired tone: {tone}
Content goal: {goal}
Target duration: {est_duration} seconds

Key improvements needed:
{recommendations}

Write an improved video script in JSON format:
{{
  "title": "Improved video title",
  "hook": "Opening 3-5 second hook statement",
  "sections": [
    {{"type": "hook", "text": "...", "estimated_duration": 5}},
    {{"type": "body", "text": "...", "estimated_duration": 50}},
    {{"type": "cta", "text": "...", "estimated_duration": 5}}
  ],
  "full_script": "Complete script text",
  "estimated_duration": {est_duration},
  "changes": ["List of what was improved"]
}}"""

    result_text = generator.generate(prompt, max_new_tokens=1024)

    # Parse JSON from response
    import json, re
    json_match = re.search(r'\{.*\}', result_text, re.DOTALL)
    if json_match:
        data = json.loads(json_match.group())
        return _validate_script_output(data, est_duration)

    raise ValueError("LLM did not return valid JSON")


def _generate_rule_based(
    original_text: str,
    existing_hook: str,
    hook_type: str,
    existing_cta: str,
    tone_result: Dict,
    recommendations: List[Dict],
    platform: str,
    audience: str,
    tone: str,
    est_duration: int,
) -> Dict:
    """Rule-based script generation as fallback."""

    # Build an improved hook
    if existing_hook:
        if hook_type == "question":
            improved_hook = existing_hook
        elif hook_type == "pain_point":
            improved_hook = f"Are you {existing_hook.lower().strip('.')}? Here's exactly what to do."
        else:
            improved_hook = f"Here's something most {audience} don't know: {existing_hook}"
    else:
        improved_hook = f"In the next {max(30, est_duration)} seconds, I'll show you exactly what you need to know to get results."

    # Build improved CTA
    platform_cta_map = {
        "YouTube": "Subscribe to the channel and hit the bell icon so you never miss a video like this.",
        "YouTube Shorts": "Follow for more short tips and double-tap if this helped!",
        "Instagram Reels": "Follow me for more content like this and save this reel for later.",
        "TikTok": "Follow for part 2 and drop a comment with your biggest question.",
        "LinkedIn": "Follow me on LinkedIn for more professional insights. Share this if it resonated.",
        "General": "If this was helpful, share it with someone who needs to see it.",
    }
    improved_cta = existing_cta if existing_cta else platform_cta_map.get(platform, platform_cta_map["General"])

    # Body content (use original transcript as base, note improvements)
    body_text = original_text[:600] if original_text else "[Body content from original video]"
    changes = [
        "Moved hook to the first 3 seconds for maximum retention",
        "Added platform-specific CTA at the end",
        "Restructured opening for immediate engagement",
    ]

    # Add recommendation-based changes
    for rec in recommendations[:3]:
        if rec.get("suggested_action"):
            changes.append(rec["suggested_action"][:100])

    hook_duration = 5
    body_duration = max(10, est_duration - 15)
    cta_duration = max(5, est_duration - body_duration - hook_duration)

    sections = [
        {"type": "hook", "text": improved_hook, "estimated_duration": hook_duration},
        {"type": "body", "text": body_text, "estimated_duration": body_duration},
        {"type": "cta", "text": improved_cta, "estimated_duration": cta_duration},
    ]

    full_script = f"{improved_hook}\n\n{body_text}\n\n{improved_cta}"

    return {
        "title": "Improved Script",
        "hook": improved_hook,
        "sections": sections,
        "full_script": full_script,
        "estimated_duration": est_duration,
        "changes": changes[:6],
        "platform": platform,
        "tone": tone,
        "version": 1,
    }


def _validate_script_output(data: Dict, est_duration: int) -> Dict:
    """Validate and clean LLM script output."""
    return {
        "title": str(data.get("title", "Improved Script"))[:200],
        "hook": str(data.get("hook", ""))[:500],
        "sections": data.get("sections", []),
        "full_script": str(data.get("full_script", ""))[:5000],
        "estimated_duration": int(data.get("estimated_duration", est_duration)),
        "changes": [str(c)[:200] for c in data.get("changes", [])[:8]],
        "version": 1,
    }

"""
Tone & Sentiment Analysis Service.
Uses the emotion provider + rule-based tone classification.
"""
from __future__ import annotations
from typing import List, Dict, Any
from app.core.logging import get_logger

logger = get_logger(__name__)

TONE_MAP = {
    "joy": "Upbeat",
    "motivation": "Motivational",
    "confidence": "Confident",
    "neutral": "Informative",
    "surprise": "Energetic",
    "anger": "Intense",
    "sadness": "Reflective",
    "fear": "Cautionary",
    "disgust": "Critical",
    "humor": "Humorous",
}

SENTIMENT_MAP = {
    "joy": "Positive",
    "motivation": "Positive",
    "confidence": "Positive",
    "surprise": "Positive",
    "humor": "Positive",
    "neutral": "Neutral",
    "anger": "Negative",
    "sadness": "Negative",
    "fear": "Negative",
    "disgust": "Negative",
}


def analyze_tone(
    transcript_segments: List[Dict],
    emotion_provider,
    full_text: str = "",
) -> Dict[str, Any]:
    """
    Analyze tone, sentiment, and emotion from transcript segments.
    """
    if not transcript_segments:
        return {
            "primary_tone": "Unknown",
            "sentiment": "Neutral",
            "emotions": {"neutral": 1.0},
            "energy_score": 50.0,
            "clarity_score": 50.0,
            "confidence_score": 50.0,
            "observations": ["Insufficient transcript for tone analysis."],
        }

    # Extract segment texts
    texts = [s.get("text", "") for s in transcript_segments if s.get("text", "").strip()]

    if not texts:
        return {
            "primary_tone": "Unknown",
            "sentiment": "Neutral",
            "emotions": {"neutral": 1.0},
            "energy_score": 50.0,
            "clarity_score": 50.0,
            "confidence_score": 50.0,
            "observations": [],
        }

    # Batch emotion classification
    try:
        segment_emotions = emotion_provider.classify_segments(texts)
        aggregated = emotion_provider.aggregate(segment_emotions)
    except Exception as e:
        logger.warning(f"Emotion analysis failed: {e}")
        aggregated = {
            "dominant": "neutral",
            "secondary": [],
            "scores": {"neutral": 1.0},
            "variation": 0.0,
        }

    dominant = aggregated.get("dominant", "neutral")
    secondary = aggregated.get("secondary", [])
    scores = aggregated.get("scores", {"neutral": 1.0})
    variation = aggregated.get("variation", 0.0)

    primary_tone = TONE_MAP.get(dominant, "Informative")
    sentiment = SENTIMENT_MAP.get(dominant, "Neutral")

    # Energy score — based on emotion variance + dominant emotion type
    energetic_emotions = {"joy", "surprise", "motivation", "anger"}
    calm_emotions = {"neutral", "sadness"}
    if dominant in energetic_emotions:
        energy_score = 70.0 + min(30, variation * 100)
    elif dominant in calm_emotions:
        energy_score = max(20.0, 50.0 - variation * 20)
    else:
        energy_score = 55.0 + variation * 10
    energy_score = round(min(100.0, max(0.0, energy_score)), 1)

    # Clarity score — based on words per segment
    avg_words = sum(len(t.split()) for t in texts) / len(texts) if texts else 0
    if 8 <= avg_words <= 20:
        clarity_score = 80.0
    elif avg_words < 4:
        clarity_score = 50.0
    elif avg_words > 40:
        clarity_score = 65.0
    else:
        clarity_score = 70.0
    clarity_score = round(clarity_score, 1)

    # Confidence score
    confident_emotions = {"confidence", "motivation", "joy"}
    if dominant in confident_emotions:
        confidence_score = 75.0 + scores.get(dominant, 0.5) * 20
    elif dominant in {"fear", "sadness"}:
        confidence_score = 40.0 + scores.get(dominant, 0.5) * 10
    else:
        confidence_score = 60.0 + scores.get(dominant, 0.5) * 10
    confidence_score = round(min(100.0, max(0.0, confidence_score)), 1)

    observations = _build_observations(dominant, secondary, scores, variation, texts)

    return {
        "primary_tone": primary_tone,
        "sentiment": sentiment,
        "emotions": scores,
        "energy_score": energy_score,
        "clarity_score": clarity_score,
        "confidence_score": confidence_score,
        "observations": observations,
    }


def _build_observations(dominant, secondary, scores, variation, texts) -> List[str]:
    obs = []
    obs.append(f"Dominant emotion is '{dominant}' — detected in the majority of transcript segments.")
    if secondary:
        obs.append(f"Secondary emotions include {', '.join(secondary)}, adding depth to delivery.")
    if variation > 0.3:
        obs.append("High emotional variation — the delivery shifts significantly throughout the video, which can maintain viewer interest.")
    elif variation < 0.1:
        obs.append("Consistent emotional tone throughout the video. Consider adding variation to maintain viewer engagement.")
    if dominant in {"anger", "fear", "disgust"}:
        obs.append("Caution: Negative emotional tone detected. Ensure this is intentional for your content style.")
    return obs

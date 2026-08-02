"""Emotion classification provider using j-hartmann/emotion-english-distilroberta-base."""
from __future__ import annotations
from typing import List, Dict, Any
from app.core.logging import get_logger

logger = get_logger(__name__)

EMOTION_LABELS = ["joy", "surprise", "anger", "sadness", "fear", "disgust", "neutral"]


class EmotionProvider:
    def __init__(self, model_name: str = "j-hartmann/emotion-english-distilroberta-base", device: str = "cpu"):
        self.model_name = model_name
        self.device = device
        self._pipeline = None

    def _load(self):
        if self._pipeline is None:
            try:
                from transformers import pipeline
                device_id = 0 if self.device == "cuda" else -1
                logger.info(f"Loading emotion model: {self.model_name}")
                self._pipeline = pipeline(
                    "text-classification",
                    model=self.model_name,
                    top_k=None,
                    device=device_id,
                )
                logger.info("Emotion model loaded.")
            except Exception as e:
                logger.error(f"Failed to load emotion model: {e}")
                raise
        return self._pipeline

    def classify_segment(self, text: str) -> Dict[str, float]:
        """Classify emotions in a single text segment."""
        if not text or len(text.strip()) < 5:
            return {"neutral": 1.0}
        try:
            pipe = self._load()
            results = pipe(text[:512])[0]  # limit to 512 chars
            return {r["label"].lower(): round(r["score"], 4) for r in results}
        except Exception as e:
            logger.warning(f"Emotion classification failed: {e}")
            return {"neutral": 1.0}

    def classify_segments(self, texts: List[str], batch_size: int = 16) -> List[Dict[str, float]]:
        """Batch classify multiple segments."""
        if not texts:
            return []
        # Truncate each text
        truncated = [t[:512] if t else "" for t in texts]
        # Filter empty
        results = []
        pipe = self._load()
        batch = [t for t in truncated if t.strip()]
        if not batch:
            return [{"neutral": 1.0}] * len(texts)
        try:
            raw = pipe(batch, batch_size=batch_size)
            for item in raw:
                results.append({r["label"].lower(): round(r["score"], 4) for r in item})
        except Exception as e:
            logger.warning(f"Batch emotion classification failed: {e}")
            results = [{"neutral": 1.0}] * len(batch)
        # Re-insert empty slots
        out = []
        bi = 0
        for t in truncated:
            if t.strip():
                out.append(results[bi] if bi < len(results) else {"neutral": 1.0})
                bi += 1
            else:
                out.append({"neutral": 1.0})
        return out

    def aggregate(self, segment_emotions: List[Dict[str, float]]) -> Dict[str, Any]:
        """Aggregate segment-level emotions into a video-level summary."""
        if not segment_emotions:
            return {"dominant": "neutral", "secondary": [], "scores": {"neutral": 1.0}, "variation": 0.0}

        totals: Dict[str, float] = {}
        for seg in segment_emotions:
            for label, score in seg.items():
                totals[label] = totals.get(label, 0.0) + score

        # Normalize
        n = len(segment_emotions)
        averages = {k: round(v / n, 4) for k, v in totals.items()}
        sorted_emotions = sorted(averages.items(), key=lambda x: x[1], reverse=True)

        dominant = sorted_emotions[0][0] if sorted_emotions else "neutral"
        secondary = [e[0] for e in sorted_emotions[1:3] if e[1] > 0.1]

        # Emotional variation (std of dominant emotion across segments)
        import statistics
        dominant_scores = [seg.get(dominant, 0.0) for seg in segment_emotions]
        variation = round(statistics.stdev(dominant_scores), 4) if len(dominant_scores) > 1 else 0.0

        return {
            "dominant": dominant,
            "secondary": secondary,
            "scores": averages,
            "variation": variation,
        }

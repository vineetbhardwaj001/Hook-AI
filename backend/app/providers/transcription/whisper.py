"""
Transcription Provider — base class + Faster-Whisper implementation with word-level precision.
"""
from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any
from app.core.logging import get_logger

logger = get_logger(__name__)


class TranscriptionProvider(ABC):
    @abstractmethod
    def transcribe(self, audio_path: str, language: Optional[str] = None) -> dict:
        """
        Returns:
        {
            "language": "en",
            "duration": 52.8,
            "words_count": 120,
            "wpm": 136.4,
            "full_text": "...",
            "words": [{"word": "hello", "start": 0.1, "end": 0.4}],
            "segments": [{"id": 1, "start": 0.0, "end": 3.2, "text": "...", "words": [...]}]
        }
        """
        ...


class FasterWhisperProvider(TranscriptionProvider):
    def __init__(
        self, 
        model_size: str = "tiny", 
        device: str = "cpu", 
        compute_type: str = "int8"
    ):
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self._model = None

    def _load(self):
        if self._model is None:
            try:
                from faster_whisper import WhisperModel
                logger.info(f"Loading faster-whisper model: {self.model_size} on {self.device}")
                self._model = WhisperModel(
                    self.model_size,
                    device=self.device,
                    compute_type=self.compute_type,
                )
                logger.info("faster-whisper model loaded successfully.")
            except ImportError:
                logger.warning("faster-whisper not installed. Falling back to HuggingFace Whisper.")
                self._model = self._load_hf_whisper()
            except Exception as e:
                logger.error(f"Failed to load faster-whisper ({e}). Falling back to HuggingFace Whisper.")
                self._model = self._load_hf_whisper()
        return self._model

    def _load_hf_whisper(self):
        """Fallback: HuggingFace transformers Whisper pipeline."""
        from transformers import pipeline
        import torch
        device = 0 if self.device == "cuda" else -1
        model_name = f"openai/whisper-{self.model_size}"
        logger.info(f"Loading HuggingFace Whisper: {model_name}")
        return pipeline(
            "automatic-speech-recognition",
            model=model_name,
            device=device,
            return_timestamps="word",
        )

    def transcribe(self, audio_path: str, language: Optional[str] = None) -> dict:
        model = self._load()

        # ── 1. Faster-Whisper API (With Word-Level Timestamps) ──────────────────
        if hasattr(model, "transcribe") and hasattr(model, "supported_languages"):
            kwargs = {
                "beam_size": 1,            # Optimized for speed & low RAM
                "word_timestamps": True,   # Enables exact word timing
                "vad_filter": True,        # Ignores silent gaps
            }
            if language:
                kwargs["language"] = language

            segments_gen, info = model.transcribe(audio_path, **kwargs)
            
            segments: List[Dict[str, Any]] = []
            all_words: List[Dict[str, Any]] = []
            full_text_parts: List[str] = []

            for i, seg in enumerate(segments_gen):
                clean_text = seg.text.strip()
                if clean_text:
                    full_text_parts.append(clean_text)

                seg_words = []
                if hasattr(seg, "words") and seg.words:
                    for w in seg.words:
                        w_text = w.word.strip()
                        if w_text:
                            w_dict = {
                                "word": w_text,
                                "start": round(w.start, 2),
                                "end": round(w.end, 2),
                                "confidence": round(getattr(w, "probability", 1.0), 2),
                            }
                            seg_words.append(w_dict)
                            all_words.append(w_dict)

                segments.append({
                    "id": i + 1,
                    "start": round(seg.start, 2),
                    "end": round(seg.end, 2),
                    "text": clean_text,
                    "words": seg_words,
                })

            duration = round(getattr(info, "duration", 0.0), 2)
            if not duration and segments:
                duration = round(segments[-1]["end"], 2)

            total_words = len(all_words)
            wpm = round((total_words / (duration / 60)), 1) if duration > 0 else 0.0

            return {
                "language": getattr(info, "language", language or "en"),
                "duration": duration,
                "words_count": total_words,
                "wpm": wpm,
                "full_text": " ".join(full_text_parts),
                "words": all_words,
                "segments": segments,
            }

        # ── 2. HuggingFace Pipeline Fallback ───────────────────────────────────
        result = model(audio_path, return_timestamps="word")
        full_text = result.get("text", "").strip()
        chunks = result.get("chunks", [])

        segments = []
        all_words = []

        for i, chunk in enumerate(chunks):
            ts = chunk.get("timestamp", (0, 0))
            start_t = round(ts[0] or 0, 2)
            end_t = round(ts[1] or 0, 2)
            word_str = chunk.get("text", "").strip()

            word_obj = {
                "word": word_str,
                "start": start_t,
                "end": end_t,
                "confidence": round(float(chunk.get("score", 0.92)), 2),
            }
            if word_str:
                all_words.append(word_obj)

            segments.append({
                "id": i + 1,
                "start": start_t,
                "end": end_t,
                "text": word_str,
                "words": [word_obj],
            })

        duration = round(segments[-1]["end"] if segments else 0, 2)
        total_words = len(all_words)
        wpm = round((total_words / (duration / 60)), 1) if duration > 0 else 0.0

        return {
            "language": language or "en",
            "duration": duration,
            "words_count": total_words,
            "wpm": wpm,
            "full_text": full_text,
            "words": all_words,
            "segments": segments,
        }
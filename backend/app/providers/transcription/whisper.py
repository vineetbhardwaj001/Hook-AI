"""
Transcription Provider — base class + Faster-Whisper implementation.
"""
from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Optional
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
            "full_text": "...",
            "segments": [{"id":1,"start":0.0,"end":3.2,"text":"..."}]
        }
        """
        ...


class FasterWhisperProvider(TranscriptionProvider):
    def __init__(self, model_size: str = "base", device: str = "cpu", compute_type: str = "int8"):
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
                logger.info("faster-whisper model loaded.")
            except ImportError:
                logger.warning("faster-whisper not installed. Falling back to HuggingFace Whisper.")
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
            return_timestamps=True,
        )

    def transcribe(self, audio_path: str, language: Optional[str] = None) -> dict:
        model = self._load()

        # Faster-whisper API
        if hasattr(model, "transcribe") and hasattr(model, "supported_languages"):
            kwargs = {"beam_size": 5}
            if language:
                kwargs["language"] = language
            segments_gen, info = model.transcribe(audio_path, **kwargs)
            segments = []
            full_text_parts = []
            for i, seg in enumerate(segments_gen):
                segments.append({
                    "id": i + 1,
                    "start": round(seg.start, 2),
                    "end": round(seg.end, 2),
                    "text": seg.text.strip(),
                })
                full_text_parts.append(seg.text.strip())
            return {
                "language": info.language,
                "duration": round(info.duration, 2),
                "full_text": " ".join(full_text_parts),
                "segments": segments,
            }

        # HuggingFace pipeline API
        result = model(audio_path, return_timestamps=True)
        full_text = result.get("text", "").strip()
        chunks = result.get("chunks", [])
        segments = []
        for i, chunk in enumerate(chunks):
            ts = chunk.get("timestamp", (0, 0))
            segments.append({
                "id": i + 1,
                "start": round(ts[0] or 0, 2),
                "end": round(ts[1] or 0, 2),
                "text": chunk.get("text", "").strip(),
            })
        return {
            "language": language or "en",
            "duration": round(segments[-1]["end"] if segments else 0, 2),
            "full_text": full_text,
            "segments": segments,
        }

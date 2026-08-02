"""
Model Manager — singleton that manages lazy loading of all AI models.
Respects HOOK_AI_DEVICE and HOOK_AI_PROFILE environment settings.
"""
from __future__ import annotations
from typing import Optional
from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


def _resolve_device() -> str:
    device = settings.hook_ai_device.lower()
    if device == "auto":
        try:
            import torch
            return "cuda" if torch.cuda.is_available() else "cpu"
        except ImportError:
            return "cpu"
    return device


def _resolve_whisper_size() -> str:
    profile = settings.hook_ai_profile.lower()
    size = settings.whisper_model_size.lower()
    if profile == "light":
        return "tiny" if size not in ("tiny", "base") else size
    elif profile == "quality":
        return "medium" if size == "base" else size
    return size  # balanced — use configured size


class ModelManager:
    """
    Singleton that lazily loads and caches AI models.
    Models are loaded once per worker process.
    """
    _instance: Optional["ModelManager"] = None
    _initialized: bool = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._device = _resolve_device()
        self._whisper: Optional[object] = None
        self._embedder: Optional[object] = None
        self._emotion: Optional[object] = None
        self._vision: Optional[object] = None
        self._generator: Optional[object] = None
        logger.info(f"ModelManager initialized | device={self._device} | profile={settings.hook_ai_profile}")

    @property
    def device(self) -> str:
        return self._device

    def get_transcription_provider(self):
        if self._whisper is None:
            from app.providers.transcription.whisper import FasterWhisperProvider
            size = _resolve_whisper_size()
            compute = "float16" if self._device == "cuda" else "int8"
            self._whisper = FasterWhisperProvider(
                model_size=size,
                device=self._device,
                compute_type=compute,
            )
            logger.info(f"Whisper provider ready: size={size}")
        return self._whisper

    def get_embedding_provider(self):
        if self._embedder is None:
            from app.providers.embeddings.sentence_transformer import EmbeddingProvider
            self._embedder = EmbeddingProvider(model_name=settings.embedding_model)
            logger.info(f"Embedding provider ready: {settings.embedding_model}")
        return self._embedder

    def get_emotion_provider(self):
        if self._emotion is None:
            from app.providers.emotion.distilroberta import EmotionProvider
            self._emotion = EmotionProvider(
                model_name=settings.emotion_model,
                device=self._device,
            )
            logger.info(f"Emotion provider ready: {settings.emotion_model}")
        return self._emotion

    def get_vision_provider(self):
        """Vision model is optional — returns None if profile is light."""
        if settings.hook_ai_profile.lower() == "light":
            return None
        if self._vision is None:
            try:
                from app.providers.vision.qwen_vl import QwenVisionProvider
                self._vision = QwenVisionProvider(
                    model_name=settings.vision_model,
                    device=self._device,
                )
                logger.info(f"Vision provider ready: {settings.vision_model}")
            except Exception as e:
                logger.warning(f"Vision provider could not be loaded: {e}. Visual analysis will be limited.")
                self._vision = None
        return self._vision

    def get_generation_provider(self):
        if self._generator is None:
            try:
                from app.providers.generation.huggingface import HuggingFaceGenerationProvider
                self._generator = HuggingFaceGenerationProvider(
                    model_name=settings.text_generation_model,
                    device=self._device,
                )
                logger.info(f"Generation provider ready: {settings.text_generation_model}")
            except Exception as e:
                logger.warning(f"Generation provider failed to load: {e}. Script generation will use fallback.")
                self._generator = None
        return self._generator

    def unload_vision(self):
        """Free GPU memory used by vision model."""
        if self._vision is not None:
            try:
                del self._vision
                self._vision = None
                import torch; torch.cuda.empty_cache()
                logger.info("Vision model unloaded.")
            except Exception:
                pass

    def unload_generator(self):
        """Free GPU memory used by text generator."""
        if self._generator is not None:
            try:
                del self._generator
                self._generator = None
                import torch; torch.cuda.empty_cache()
                logger.info("Generator model unloaded.")
            except Exception:
                pass


# Global singleton instance
_manager: Optional[ModelManager] = None


def get_model_manager() -> ModelManager:
    global _manager
    if _manager is None:
        _manager = ModelManager()
    return _manager

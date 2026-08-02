"""HuggingFace text generation provider (Phi-3 or similar)."""
from __future__ import annotations
from typing import Optional
from app.core.logging import get_logger

logger = get_logger(__name__)


class HuggingFaceGenerationProvider:
    def __init__(self, model_name: str = "microsoft/Phi-3-mini-4k-instruct", device: str = "cpu"):
        self.model_name = model_name
        self.device = device
        self._pipeline = None

    def _load(self):
        if self._pipeline is None:
            try:
                from transformers import pipeline, AutoTokenizer, AutoModelForCausalLM
                import torch
                logger.info(f"Loading text generation model: {self.model_name}")
                device_id = 0 if self.device == "cuda" else -1
                self._pipeline = pipeline(
                    "text-generation",
                    model=self.model_name,
                    device_map="auto" if self.device == "cuda" else None,
                    torch_dtype=torch.float16 if self.device == "cuda" else torch.float32,
                    trust_remote_code=True,
                )
                logger.info(f"Text generation model loaded: {self.model_name}")
            except Exception as e:
                logger.error(f"Failed to load generation model: {e}")
                raise
        return self._pipeline

    def generate(self, prompt: str, max_new_tokens: int = 512, temperature: float = 0.7) -> str:
        pipe = self._load()
        messages = [{"role": "user", "content": prompt}]
        try:
            result = pipe(
                messages,
                max_new_tokens=max_new_tokens,
                do_sample=True,
                temperature=temperature,
                top_p=0.9,
                return_full_text=False,
            )
            if result and isinstance(result, list):
                generated = result[0].get("generated_text", "")
                if isinstance(generated, list):
                    return generated[-1].get("content", "") if generated else ""
                return str(generated)
        except Exception as e:
            logger.warning(f"Text generation failed: {e}")
            raise
        return ""

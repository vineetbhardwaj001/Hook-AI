"""Qwen Vision Language Model provider (optional)."""
from __future__ import annotations
from typing import Optional, List
from app.core.logging import get_logger

logger = get_logger(__name__)


class QwenVisionProvider:
    def __init__(self, model_name: str = "Qwen/Qwen3-VL-4B-Instruct", device: str = "cpu"):
        self.model_name = model_name
        self.device = device
        self._model = None
        self._processor = None

    def _load(self):
        if self._model is None:
            try:
                from transformers import AutoProcessor, AutoModelForVision2Seq
                import torch
                logger.info(f"Loading vision model: {self.model_name}")
                self._processor = AutoProcessor.from_pretrained(self.model_name, trust_remote_code=True)
                self._model = AutoModelForVision2Seq.from_pretrained(
                    self.model_name,
                    torch_dtype=torch.float16 if self.device == "cuda" else torch.float32,
                    device_map="auto" if self.device == "cuda" else None,
                    trust_remote_code=True,
                )
                if self.device != "cuda":
                    self._model = self._model.to("cpu")
                logger.info("Vision model loaded.")
            except Exception as e:
                logger.error(f"Failed to load vision model: {e}")
                raise
        return self._model, self._processor

    def analyze_frame(self, image_path: str, prompt: str = None) -> str:
        """Analyze a single frame with the vision model."""
        model, processor = self._load()
        from PIL import Image
        import torch

        image = Image.open(image_path).convert("RGB")
        if not prompt:
            prompt = "Describe this video frame. What is happening? Is there text, graphics, or people visible? Is it visually engaging?"

        inputs = processor(text=prompt, images=image, return_tensors="pt")
        if self.device == "cuda":
            inputs = inputs.to("cuda")

        with torch.no_grad():
            outputs = model.generate(**inputs, max_new_tokens=150, do_sample=False)

        result = processor.decode(outputs[0], skip_special_tokens=True)
        # Remove the input prompt from output
        if prompt in result:
            result = result.replace(prompt, "").strip()
        return result

    def analyze_frames_batch(self, image_paths: List[str]) -> List[str]:
        """Analyze multiple frames. Returns descriptions."""
        results = []
        for path in image_paths[:5]:  # Limit to 5 frames to manage memory
            try:
                desc = self.analyze_frame(path)
                results.append(desc)
            except Exception as e:
                logger.warning(f"Vision analysis failed for {path}: {e}")
                results.append("")
        return results

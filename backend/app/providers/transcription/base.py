from abc import ABC, abstractmethod
from typing import Optional

class TranscriptionProvider(ABC):
    @abstractmethod
    def transcribe(self, audio_path: str, language: Optional[str] = None) -> dict: ...

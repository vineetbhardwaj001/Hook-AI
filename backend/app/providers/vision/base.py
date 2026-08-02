from abc import ABC, abstractmethod
from typing import List

class BaseVisionProvider(ABC):
    @abstractmethod
    def analyze_frame(self, image_path: str, prompt: str = None) -> str: ...

from abc import ABC, abstractmethod

class BaseGenerationProvider(ABC):
    @abstractmethod
    def generate(self, prompt: str, max_new_tokens: int = 512) -> str: ...

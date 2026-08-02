"""Sentence Transformers embedding provider."""
from __future__ import annotations
from typing import List
from app.core.logging import get_logger

logger = get_logger(__name__)


class EmbeddingProvider:
    def __init__(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2"):
        self.model_name = model_name
        self._model = None

    def _load(self):
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
                logger.info(f"Loading SentenceTransformer: {self.model_name}")
                self._model = SentenceTransformer(self.model_name)
                logger.info("SentenceTransformer loaded.")
            except ImportError:
                raise ImportError("sentence-transformers not installed.")
        return self._model

    def embed(self, texts: List[str]) -> List[List[float]]:
        model = self._load()
        embeddings = model.encode(texts, convert_to_numpy=True, show_progress_bar=False)
        return embeddings.tolist()

    def similarity(self, text_a: str, text_b: str) -> float:
        """Cosine similarity between two texts."""
        import numpy as np
        vecs = self._load().encode([text_a, text_b], convert_to_numpy=True)
        a, b = vecs[0], vecs[1]
        denom = (np.linalg.norm(a) * np.linalg.norm(b))
        if denom == 0:
            return 0.0
        return float(np.dot(a, b) / denom)

    def batch_similarity(self, query: str, candidates: List[str]) -> List[float]:
        """Return cosine similarities of query vs each candidate."""
        import numpy as np
        all_texts = [query] + candidates
        vecs = self._load().encode(all_texts, convert_to_numpy=True)
        q_vec = vecs[0]
        q_norm = np.linalg.norm(q_vec)
        results = []
        for i in range(1, len(vecs)):
            c_vec = vecs[i]
            c_norm = np.linalg.norm(c_vec)
            denom = q_norm * c_norm
            results.append(float(np.dot(q_vec, c_vec) / denom) if denom > 0 else 0.0)
        return results

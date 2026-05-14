from typing import List, Optional
from ..core.logging_config import get_logger

logger = get_logger(__name__)


class EmbeddingManager:
    """Manages text embeddings using sentence-transformers."""

    DEFAULT_MODEL = "all-MiniLM-L6-v2"

    def __init__(self, model_name: str = DEFAULT_MODEL, device: str = "cpu", cache_size: int = 1000):
        self.model_name = model_name
        self.device = device
        self.cache_size = cache_size
        self._model = None
        self.model = None  # public alias for patching in tests
        self.cache: dict = {}  # public cache dict

    def _load_model(self):
        # Allow tests to patch self.model directly
        if self.model is not None:
            return self.model
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
                self._model = SentenceTransformer(self.model_name, device=self.device)
                self.model = self._model
                logger.info(f"Loaded embedding model '{self.model_name}' on {self.device}")
            except ImportError:
                raise ImportError("sentence-transformers is required: pip install sentence-transformers")
        return self._model

    async def embed_text(self, text: str) -> List[float]:
        if text in self.cache:
            return self.cache[text]
        model = self._load_model()
        raw = model.encode([text])
        result = list(raw[0]) if hasattr(raw[0], '__iter__') else list(raw[0])
        if len(self.cache) < self.cache_size:
            self.cache[text] = result
        return result

    def embed(self, text: str) -> List[float]:
        if text in self.cache:
            return self.cache[text]
        model = self._load_model()
        embedding = model.encode(text, convert_to_numpy=True)
        result = embedding.tolist()
        if len(self.cache) < self.cache_size:
            self.cache[text] = result
        return result

    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        model = self._load_model()
        raw = model.encode(texts)
        return [list(e) for e in raw]

    def clear_cache(self) -> None:
        self.cache.clear()

    def get_cache_size(self) -> int:
        return len(self.cache)

    def get_model_info(self) -> dict:
        return {
            "model_name": self.model_name,
            "device": self.device,
            "loaded": self._model is not None,
            "cache_entries": len(self.cache)
        }

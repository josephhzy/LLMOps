"""Embedding service — wraps sentence-transformers with lazy-loaded singleton.

Implements the Embedder port. Model downloads on first use (~90MB for all-MiniLM-L6-v2).
"""

from __future__ import annotations

import threading

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_model_cache: dict[str, object] = {}
_model_lock = threading.Lock()


class EmbeddingService:
    """Manages embedding model lifecycle and inference."""

    def __init__(self, model_name: str | None = None, device: str | None = None) -> None:
        self.model_name = model_name or settings.embedding_model
        self.device = device or settings.embedding_device

    def _get_model(self):
        """Lazy-load model singleton. Downloads on first call. Thread-safe."""
        if self.model_name not in _model_cache:
            with _model_lock:
                # Double-check after acquiring the lock
                if self.model_name not in _model_cache:
                    from sentence_transformers import SentenceTransformer

                    logger.info(
                        'Loading embedding model (one-time download if not cached)',
                        model_name=self.model_name,
                    )
                    _model_cache[self.model_name] = SentenceTransformer(self.model_name, device=self.device)
        return _model_cache[self.model_name]

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Encode a batch of texts into dense vectors."""
        if not texts:
            return []
        model = self._get_model()
        embeddings = model.encode(texts, show_progress_bar=False, convert_to_numpy=True)
        return embeddings.tolist()

    def embed_query(self, query: str) -> list[float]:
        """Encode a single query. Separate method for future query-specific prefixing."""
        return self.embed_texts([query])[0]

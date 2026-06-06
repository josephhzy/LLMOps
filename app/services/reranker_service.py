"""Reranker service — second-stage relevance scoring.

Implements the Reranker port with two switchable backends:
- tfidf (default): zero model download, uses sklearn TF-IDF + cosine similarity
- cross_encoder: higher quality, requires sentence-transformers model download (~90MB)
"""

from __future__ import annotations

import threading
from dataclasses import replace

from app.core.config import settings
from app.core.logging import get_logger
from app.models.domain import RetrievedChunk

logger = get_logger(__name__)

_cross_encoder_cache: dict[str, object] = {}
_cross_encoder_lock = threading.Lock()


class RerankerService:
    """Second-stage reranking with configurable backend."""

    def __init__(self) -> None:
        self.backend = settings.reranker_backend

    async def rerank(self, query: str, chunks: list[RetrievedChunk]) -> list[RetrievedChunk]:
        """Rerank chunks using the configured backend."""
        if not chunks or len(chunks) <= 1:
            return chunks

        if self.backend == 'cross_encoder':
            return self._rerank_cross_encoder(query, chunks)
        return self._rerank_tfidf(query, chunks)

    def rerank_sync(self, query: str, chunks: list[RetrievedChunk]) -> list[RetrievedChunk]:
        """Synchronous rerank — same logic as rerank() for use in offline pipelines."""
        if not chunks or len(chunks) <= 1:
            return chunks

        if self.backend == 'cross_encoder':
            return self._rerank_cross_encoder(query, chunks)
        return self._rerank_tfidf(query, chunks)

    def _rerank_tfidf(self, query: str, chunks: list[RetrievedChunk]) -> list[RetrievedChunk]:
        """TF-IDF cosine similarity reranking. Zero model download required."""
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity

        corpus = [query] + [c.content for c in chunks]
        vectorizer = TfidfVectorizer(stop_words='english')
        tfidf_matrix = vectorizer.fit_transform(corpus)

        query_vec = tfidf_matrix[0:1]
        chunk_vecs = tfidf_matrix[1:]
        similarities = cosine_similarity(query_vec, chunk_vecs).flatten()

        reranked = []
        for chunk, sim_score in zip(chunks, similarities, strict=True):
            # Blend original retrieval score with reranker score
            blended = round(0.4 * chunk.score + 0.6 * float(sim_score), 4)
            reranked.append(replace(chunk, score=blended))

        reranked.sort(key=lambda c: c.score, reverse=True)
        logger.info('TF-IDF reranked chunks', count=len(reranked))
        return reranked

    def _rerank_cross_encoder(self, query: str, chunks: list[RetrievedChunk]) -> list[RetrievedChunk]:
        """Cross-encoder reranking. Higher quality, requires model download. Thread-safe."""
        from sentence_transformers import CrossEncoder

        model_name = settings.cross_encoder_model
        if model_name not in _cross_encoder_cache:
            with _cross_encoder_lock:
                # Double-check after acquiring the lock
                if model_name not in _cross_encoder_cache:
                    logger.info('Loading cross-encoder model', model_name=model_name)
                    _cross_encoder_cache[model_name] = CrossEncoder(model_name)

        model = _cross_encoder_cache[model_name]
        pairs = [(query, c.content) for c in chunks]
        scores = model.predict(pairs)

        reranked = []
        for chunk, score in zip(chunks, scores, strict=True):
            reranked.append(replace(chunk, score=round(float(score), 4)))

        reranked.sort(key=lambda c: c.score, reverse=True)
        logger.info('Cross-encoder reranked chunks', count=len(reranked))
        return reranked

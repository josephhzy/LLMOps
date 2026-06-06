"""Retrieval service — search and evidence preparation layer.

Depends on VectorStore and Embedder ports, not directly on ChromaDB.
Automatically excludes non-active (revoked and superseded) documents from results.
Constructor accepts ports for dependency injection; defaults to concrete impls.
"""

from __future__ import annotations

import time

from app.core.logging import get_logger
from app.core.metrics import RETRIEVAL_LATENCY, RETRIEVAL_RESULTS
from app.domain.models import DocumentStatus
from app.domain.ports import Embedder, VectorStore
from app.models.domain import RetrievedChunk
from app.services.embedding_service import EmbeddingService
from app.services.vector_store import ChromaVectorStore

logger = get_logger(__name__)


class RetrievalService:
    """Search and evidence preparation layer."""

    def __init__(
        self,
        embedder: Embedder | None = None,
        store: VectorStore | None = None,
    ) -> None:
        self.embedder = embedder or EmbeddingService()
        self.store = store or ChromaVectorStore()

    async def search(
        self,
        query: str,
        top_k: int,
        role: str,
        requested_sources: list[str],
    ) -> list[RetrievedChunk]:
        """Run vector search with ACL and source filtering.

        Excludes non-active (revoked and superseded) documents automatically. Returns empty list
        if the vector store has no data (pre-ingestion state).
        """
        start = time.perf_counter()
        query_embedding = self.embedder.embed_query(query)

        # Build metadata filter: only return active documents (excludes revoked and superseded)
        where_filter = {'document_status': {'$eq': DocumentStatus.ACTIVE}}

        chunks = self.store.search(
            query_embedding=query_embedding,
            top_k=top_k,
            where_filter=where_filter,
        )

        if requested_sources:
            chunks = [c for c in chunks if c.metadata.get('doc_id') in set(requested_sources)]

        chunks = self.apply_acl_filter(chunks, role)
        RETRIEVAL_LATENCY.observe(time.perf_counter() - start)
        RETRIEVAL_RESULTS.observe(len(chunks))
        logger.info('Retrieved chunks for query', count=len(chunks), role=role)
        return chunks

    def search_sync(
        self,
        query: str,
        top_k: int,
        role: str,
        requested_sources: list[str],
    ) -> list[RetrievedChunk]:
        """Synchronous search — same logic as search() for use in offline pipelines."""
        query_embedding = self.embedder.embed_query(query)
        where_filter = {'document_status': {'$eq': DocumentStatus.ACTIVE}}
        chunks = self.store.search(
            query_embedding=query_embedding,
            top_k=top_k,
            where_filter=where_filter,
        )
        if requested_sources:
            chunks = [c for c in chunks if c.metadata.get('doc_id') in set(requested_sources)]
        chunks = self.apply_acl_filter(chunks, role)
        logger.info('Retrieved chunks for query (sync)', count=len(chunks), role=role)
        return chunks

    def apply_acl_filter(self, chunks: list[RetrievedChunk], role: str) -> list[RetrievedChunk]:
        """Drop unauthorized chunks before prompt construction."""
        if role == 'admin':
            return chunks
        return [c for c in chunks if c.metadata.get('classification') != 'restricted']

    def prepare_context(self, chunks: list[RetrievedChunk]) -> str:
        """Turn chunks into prompt-ready evidence blocks."""
        return '\n\n'.join(f'[{i + 1}] {c.title}\n{c.content}' for i, c in enumerate(chunks))

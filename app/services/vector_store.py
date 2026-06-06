"""ChromaDB vector store — implements the VectorStore port.

Uses embedded PersistentClient (no server required). Data persists to disk
at the configured chroma_persist_dir. Gracefully handles empty collections.
"""

from __future__ import annotations

import threading
from typing import Any

import chromadb

from app.core.config import settings
from app.core.logging import get_logger
from app.models.domain import RetrievedChunk

logger = get_logger(__name__)

_client_cache: dict[str, chromadb.ClientAPI] = {}
_client_lock = threading.Lock()


class ChromaVectorStore:
    """ChromaDB implementation of the VectorStore port."""

    def __init__(
        self,
        persist_dir: str | None = None,
        collection_name: str | None = None,
    ) -> None:
        self.persist_dir = persist_dir or settings.chroma_persist_dir
        self.collection_name = collection_name or settings.chroma_collection_name

    def _get_client(self) -> chromadb.ClientAPI:
        """Get or create a ChromaDB client. Thread-safe."""
        if self.persist_dir not in _client_cache:
            with _client_lock:
                # Double-check after acquiring the lock
                if self.persist_dir not in _client_cache:
                    _client_cache[self.persist_dir] = chromadb.PersistentClient(path=self.persist_dir)
        return _client_cache[self.persist_dir]

    def _get_collection(self):
        client = self._get_client()
        return client.get_or_create_collection(
            name=self.collection_name,
            metadata={'hnsw:space': 'cosine'},
        )

    def search(
        self,
        query_embedding: list[float],
        top_k: int,
        where_filter: dict[str, Any] | None = None,
    ) -> list[RetrievedChunk]:
        """Search for similar chunks. Returns empty list if collection has no data."""
        collection = self._get_collection()
        if collection.count() == 0:
            logger.warning('Vector store is empty — run ingestion first (make ingest)')
            return []

        kwargs: dict[str, Any] = {
            'query_embeddings': [query_embedding],
            'n_results': min(top_k, collection.count()),
            'include': ['documents', 'metadatas', 'distances'],
        }
        if where_filter:
            kwargs['where'] = where_filter

        results = collection.query(**kwargs)

        chunks = []
        for i in range(len(results['ids'][0])):
            metadata = results['metadatas'][0][i] or {}
            distance = results['distances'][0][i]
            # ChromaDB cosine distance is 1 - cosine_similarity
            score = round(1.0 - distance, 4)
            chunks.append(
                RetrievedChunk(
                    doc_id=metadata.get('doc_id', ''),
                    chunk_id=results['ids'][0][i],
                    title=metadata.get('title', ''),
                    content=results['documents'][0][i],
                    score=score,
                    metadata=metadata,
                )
            )
        return chunks

    def upsert(
        self,
        ids: list[str],
        embeddings: list[list[float]],
        documents: list[str],
        metadatas: list[dict[str, Any]],
    ) -> None:
        """Insert or update chunks with their embeddings and metadata."""
        collection = self._get_collection()
        collection.upsert(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas,
        )
        logger.info('Upserted chunks', count=len(ids), collection=self.collection_name)

    def delete(self, ids: list[str]) -> None:
        """Delete chunks by ID."""
        collection = self._get_collection()
        collection.delete(ids=ids)

    def count(self) -> int:
        """Return total number of chunks in the collection."""
        return self._get_collection().count()

    def update_metadata(self, ids: list[str], metadatas: list[dict[str, Any]]) -> None:
        """Update metadata for existing chunks (e.g., mark as revoked)."""
        collection = self._get_collection()
        collection.update(ids=ids, metadatas=metadatas)

    def heartbeat(self) -> bool:
        """Check if ChromaDB is accessible."""
        try:
            self._get_client().heartbeat()
            return True
        except Exception:
            return False

"""Domain ports — abstract contracts that services implement.

These protocols define the boundaries between business logic and infrastructure.
Services depend on ports, not on concrete implementations. This enables:
- swapping ChromaDB for Milvus/PgVector without changing retrieval logic
- swapping TF-IDF reranking for cross-encoder without changing the pipeline
- testing with in-memory fakes instead of real backends
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from app.models.domain import GeneratedAnswer, RetrievedChunk


@runtime_checkable
class Embedder(Protocol):
    """Contract for text embedding backends."""

    def embed_texts(self, texts: list[str]) -> list[list[float]]: ...

    def embed_query(self, query: str) -> list[float]: ...


@runtime_checkable
class VectorStore(Protocol):
    """Contract for vector storage backends (ChromaDB, Milvus, PgVector, etc.)."""

    def search(
        self,
        query_embedding: list[float],
        top_k: int,
        where_filter: dict[str, Any] | None = None,
    ) -> list[RetrievedChunk]: ...

    def upsert(
        self,
        ids: list[str],
        embeddings: list[list[float]],
        documents: list[str],
        metadatas: list[dict[str, Any]],
    ) -> None: ...

    def delete(self, ids: list[str]) -> None: ...

    def count(self) -> int: ...

    def update_metadata(self, ids: list[str], metadatas: list[dict[str, Any]]) -> None: ...


@runtime_checkable
class Reranker(Protocol):
    """Contract for second-stage reranking backends."""

    async def rerank(self, query: str, chunks: list[RetrievedChunk]) -> list[RetrievedChunk]: ...


@runtime_checkable
class Generator(Protocol):
    """Contract for text generation backends (template, Ollama, OpenAI-compat, etc.)."""

    async def generate(self, prompt: str, task_type: str) -> GeneratedAnswer: ...


@runtime_checkable
class Verifier(Protocol):
    """Contract for grounding verification backends.

    Current implementation is a lightweight TF-IDF support heuristic.
    Interface supports future swap to NLI, claim-extraction, or citation-span verifiers.
    """

    def verify_grounding(self, answer: str, chunks: list[RetrievedChunk]) -> dict: ...


# DocumentRepository — planned port for document lifecycle management (get, list,
# update_status, revoke).  Not yet implemented or injected; define the Protocol
# here once a concrete implementation exists.

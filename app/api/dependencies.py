"""Dependency factories for FastAPI routes.

Constructs the service graph with proper dependency injection.
Uses lru_cache to ensure singleton behavior within the process.
"""

from __future__ import annotations

from functools import lru_cache

from app.services.corpus_service import CorpusService
from app.services.job_service import JobService
from app.services.model_registry import ModelRegistry
from app.services.rag_service import RAGService


@lru_cache
def get_rag_service() -> RAGService:
    """Create the RAG service with all dependencies wired up."""
    return RAGService()


@lru_cache
def get_job_service() -> JobService:
    """Singleton job service."""
    return JobService()


@lru_cache
def get_corpus_service() -> CorpusService:
    """Singleton corpus service."""
    return CorpusService()


@lru_cache
def get_model_registry() -> ModelRegistry:
    """Singleton model registry."""
    return ModelRegistry()

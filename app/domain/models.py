"""Domain value objects and enums for the LLM Ops platform.

These are pure domain concepts — no infrastructure dependencies.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class DocumentStatus(StrEnum):
    ACTIVE = 'active'
    SUPERSEDED = 'superseded'
    REVOKED = 'revoked'


class JobStatus(StrEnum):
    PENDING = 'pending'
    RUNNING = 'running'
    COMPLETED = 'completed'
    FAILED = 'failed'
    RETRYING = 'retrying'


class JobType(StrEnum):
    INGEST = 'ingest'
    EVALUATE = 'evaluate'
    REINDEX = 'reindex'
    FINETUNE = 'finetune'  # placeholder — no handler implemented in JobService yet


class PromotionStatus(StrEnum):
    CANDIDATE = 'candidate'
    SHADOW = 'shadow'
    CANARY = 'canary'
    PRODUCTION = 'production'
    REJECTED = 'rejected'


@dataclass
class CorpusVersion:
    version_id: str
    ingestion_run_id: str
    document_count: int
    chunk_count: int
    created_at: str
    status_counts: dict[str, int] = field(default_factory=dict)


@dataclass
class IngestionRun:
    run_id: str
    source_dir: str
    documents_processed: int
    chunks_created: int
    corpus_version: str
    started_at: str
    completed_at: str = ''
    errors: list[str] = field(default_factory=list)


@dataclass
class ModelRegistryEntry:
    model_id: str
    backend: str
    prompt_version: str
    embedding_model: str
    eval_snapshot: dict = field(default_factory=dict)
    status: str = 'candidate'
    registered_at: str = ''
    promoted_at: str = ''
    notes: str = ''

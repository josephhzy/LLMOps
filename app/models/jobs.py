"""Job models for async task orchestration."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from app.domain.models import JobStatus


@dataclass
class Job:
    id: str
    job_type: str
    status: str = JobStatus.PENDING
    params: dict = field(default_factory=dict)
    created_at: str = ''
    started_at: str = ''
    completed_at: str = ''
    result: dict | None = None
    error: str = ''
    retry_count: int = 0
    max_retries: int = 3

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now(UTC).isoformat()

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'job_type': self.job_type,
            'status': self.status,
            'params': self.params,
            'created_at': self.created_at,
            'started_at': self.started_at,
            'completed_at': self.completed_at,
            'result': self.result,
            'error': self.error,
            'retry_count': self.retry_count,
            'max_retries': self.max_retries,
        }

    @classmethod
    def from_dict(cls, data: dict) -> Job:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

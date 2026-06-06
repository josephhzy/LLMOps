"""Job service — file-backed async job orchestration.

Provides persistent job state, retries, and status polling.
Uses JSON file storage for demo portability. Interface supports
migration to Redis/Celery/Dramatiq for real deployments.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path

from app.core.logging import get_logger
from app.domain.models import JobStatus, JobType
from app.models.jobs import Job

logger = get_logger(__name__)

JOBS_DIR = Path('data/jobs')


class JobService:
    """File-backed job registry with submit/status/retry lifecycle."""

    def __init__(self, jobs_dir: Path | None = None) -> None:
        self.jobs_dir = jobs_dir or JOBS_DIR
        self.jobs_dir.mkdir(parents=True, exist_ok=True)

    def _job_path(self, job_id: str) -> Path:
        return self.jobs_dir / f'{job_id}.json'

    def _save(self, job: Job) -> None:
        self._job_path(job.id).write_text(json.dumps(job.to_dict(), indent=2))

    def _load(self, job_id: str) -> Job | None:
        path = self._job_path(job_id)
        if not path.exists():
            return None
        return Job.from_dict(json.loads(path.read_text()))

    def submit(self, job_type: str, params: dict | None = None) -> str:
        """Submit a new job. Returns job ID."""
        job_id = f'job-{uuid.uuid4().hex[:12]}'
        job = Job(id=job_id, job_type=job_type, params=params or {})
        self._save(job)
        logger.info('Job submitted', job_id=job_id, job_type=job_type)
        return job_id

    def get_status(self, job_id: str) -> Job | None:
        """Get current job state."""
        return self._load(job_id)

    def list_jobs(self, status_filter: str | None = None) -> list[Job]:
        """List all jobs, optionally filtered by status."""
        jobs = []
        for path in sorted(self.jobs_dir.glob('job-*.json'), reverse=True):
            try:
                job = Job.from_dict(json.loads(path.read_text()))
                if status_filter is None or job.status == status_filter:
                    jobs.append(job)
            except (json.JSONDecodeError, KeyError):
                logger.warning('Corrupt job file', path=str(path))
        return jobs

    def start(self, job_id: str) -> bool:
        """Mark job as running."""
        job = self._load(job_id)
        if not job or job.status != JobStatus.PENDING:
            return False
        job.status = JobStatus.RUNNING
        job.started_at = datetime.now(UTC).isoformat()
        self._save(job)
        logger.info('Job started', job_id=job_id)
        return True

    def complete(self, job_id: str, result: dict) -> bool:
        """Mark job as completed with result."""
        job = self._load(job_id)
        if not job:
            return False
        job.status = JobStatus.COMPLETED
        job.completed_at = datetime.now(UTC).isoformat()
        job.result = result
        self._save(job)
        logger.info('Job completed', job_id=job_id)
        return True

    def fail(self, job_id: str, error: str) -> bool:
        """Mark job as failed with error."""
        job = self._load(job_id)
        if not job:
            return False
        job.status = JobStatus.FAILED
        job.completed_at = datetime.now(UTC).isoformat()
        job.error = error
        self._save(job)
        logger.warning('Job failed', job_id=job_id, error=error)
        return True

    def retry(self, job_id: str) -> str | None:
        """Retry a failed job. Creates a new job with incremented retry count."""
        job = self._load(job_id)
        if not job or job.status != JobStatus.FAILED:
            return None
        if job.retry_count >= job.max_retries:
            logger.warning('Job exceeded max retries', job_id=job_id, max_retries=job.max_retries)
            return None

        new_id = self.submit(job.job_type, job.params)
        new_job = self._load(new_id)
        if new_job:
            new_job.retry_count = job.retry_count + 1
            self._save(new_job)

        logger.info(
            'Job retried',
            old_job_id=job_id,
            new_job_id=new_id,
            attempt=new_job.retry_count if new_job else 0,
        )
        return new_id

    def execute(self, job_id: str) -> None:
        """Execute a job synchronously. Used by worker loop."""
        job = self._load(job_id)
        if not job:
            return

        self.start(job_id)

        try:
            if job.job_type == JobType.INGEST:
                from pipelines.ingest_pipeline import run_ingest

                result = run_ingest(
                    source_dir=job.params.get('source_dir'),
                    output_dir=job.params.get('output_dir'),
                )
            elif job.job_type == JobType.EVALUATE:
                from pipelines.run_evaluation import main as run_eval

                result = run_eval()
            elif job.job_type == JobType.REINDEX:
                from pipelines.ingest_pipeline import run_ingest

                result = run_ingest()
            else:
                raise ValueError(
                    f"Unknown job type '{job.job_type}'. "
                    f'Supported types: {JobType.INGEST}, {JobType.EVALUATE}, {JobType.REINDEX}'
                )

            self.complete(job_id, result)

        except Exception as e:
            logger.error(
                'Job execution failed',
                job_id=job_id,
                job_type=job.job_type,
                error=str(e),
            )
            self.fail(job_id, str(e))

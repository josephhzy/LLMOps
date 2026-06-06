"""Ingestion API routes."""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends

from app.api.dependencies import get_job_service
from app.core.auth import AuthenticatedUser, require_admin
from app.services.job_service import JobService
from pipelines.ingest_pipeline import run_ingest

router = APIRouter()


@router.post('/ingest/rebuild-index')
async def rebuild_index(
    background_tasks: BackgroundTasks,
    user: AuthenticatedUser = Depends(require_admin),
    job_service: JobService = Depends(get_job_service),
) -> dict:
    """Trigger index rebuild as an async job."""
    job_id = job_service.submit('reindex', {})
    background_tasks.add_task(job_service.execute, job_id)
    return {'status': 'queued', 'job_type': 'reindex', 'job_id': job_id}


@router.post('/ingest/rebuild-index-sync')
async def rebuild_index_sync(
    user: AuthenticatedUser = Depends(require_admin),
) -> dict:
    """Trigger synchronous index rebuild (for testing/demo).

    After the rebuild finishes, invalidate the CorpusService singleton cache so
    downstream API calls (e.g. /v1/admin/corpus/status) see the newly persisted
    corpus state rather than the pre-rebuild snapshot.
    """
    from app.api.dependencies import get_corpus_service

    result = run_ingest()
    get_corpus_service.cache_clear()
    return {'status': 'completed', **result}

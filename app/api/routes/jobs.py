"""Job management API routes."""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel

from app.api.dependencies import get_job_service
from app.core.auth import AuthenticatedUser, require_admin
from app.services.job_service import JobService

router = APIRouter()


class JobSubmitRequest(BaseModel):
    job_type: str
    params: dict = {}


@router.post('/jobs/submit')
async def submit_job(
    request: JobSubmitRequest,
    background_tasks: BackgroundTasks,
    user: AuthenticatedUser = Depends(require_admin),
    job_service: JobService = Depends(get_job_service),
) -> dict:
    """Submit a job for async execution."""
    job_id = job_service.submit(request.job_type, request.params)
    background_tasks.add_task(job_service.execute, job_id)
    return {'job_id': job_id, 'status': 'submitted'}


@router.get('/jobs/{job_id}')
async def get_job(job_id: str, job_service: JobService = Depends(get_job_service)) -> dict:
    """Get job status and result."""
    job = job_service.get_status(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f'Job not found: {job_id}')
    return job.to_dict()


@router.get('/jobs')
async def list_jobs(status: str | None = None, job_service: JobService = Depends(get_job_service)) -> dict:
    """List jobs with optional status filter."""
    jobs = job_service.list_jobs(status_filter=status)
    return {'jobs': [j.to_dict() for j in jobs], 'total': len(jobs)}


@router.post('/jobs/{job_id}/retry')
async def retry_job(
    job_id: str,
    background_tasks: BackgroundTasks,
    user: AuthenticatedUser = Depends(require_admin),
    job_service: JobService = Depends(get_job_service),
) -> dict:
    """Retry a failed job."""
    new_id = job_service.retry(job_id)
    if not new_id:
        raise HTTPException(
            status_code=400,
            detail='Cannot retry: job not found, not failed, or max retries exceeded',
        )
    background_tasks.add_task(job_service.execute, new_id)
    return {'original_job_id': job_id, 'new_job_id': new_id, 'status': 'retrying'}

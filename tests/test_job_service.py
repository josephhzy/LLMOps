"""Job service tests."""

import pytest

from app.domain.models import JobStatus
from app.services.job_service import JobService


@pytest.fixture
def job_service(tmp_path):
    return JobService(jobs_dir=tmp_path)


def test_submit_creates_job(job_service):
    job_id = job_service.submit('ingest', {'source_dir': '/tmp/docs'})
    assert job_id.startswith('job-')
    job = job_service.get_status(job_id)
    assert job is not None
    assert job.status == JobStatus.PENDING


def test_start_marks_running(job_service):
    job_id = job_service.submit('evaluate')
    assert job_service.start(job_id) is True
    job = job_service.get_status(job_id)
    assert job.status == JobStatus.RUNNING
    assert job.started_at


def test_complete_marks_completed(job_service):
    job_id = job_service.submit('ingest')
    job_service.start(job_id)
    assert job_service.complete(job_id, {'chunks': 42}) is True
    job = job_service.get_status(job_id)
    assert job.status == JobStatus.COMPLETED
    assert job.result == {'chunks': 42}


def test_fail_marks_failed(job_service):
    job_id = job_service.submit('ingest')
    job_service.start(job_id)
    assert job_service.fail(job_id, 'connection timeout') is True
    job = job_service.get_status(job_id)
    assert job.status == JobStatus.FAILED
    assert 'timeout' in job.error


def test_retry_creates_new_job(job_service):
    job_id = job_service.submit('ingest')
    job_service.start(job_id)
    job_service.fail(job_id, 'error')
    new_id = job_service.retry(job_id)
    assert new_id is not None
    assert new_id != job_id
    new_job = job_service.get_status(new_id)
    assert new_job.retry_count == 1


def test_retry_non_failed_returns_none(job_service):
    job_id = job_service.submit('ingest')
    assert job_service.retry(job_id) is None  # Can't retry pending


def test_list_jobs_with_filter(job_service):
    job_service.submit('ingest')
    job_id2 = job_service.submit('evaluate')
    job_service.start(job_id2)

    pending = job_service.list_jobs(status_filter=JobStatus.PENDING)
    assert len(pending) == 1

    running = job_service.list_jobs(status_filter=JobStatus.RUNNING)
    assert len(running) == 1


def test_get_nonexistent_job(job_service):
    assert job_service.get_status('job-nonexistent') is None

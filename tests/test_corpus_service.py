"""Corpus service tests."""

from unittest.mock import MagicMock

import pytest

from app.domain.models import DocumentStatus
from app.services.corpus_service import CorpusService


@pytest.fixture
def corpus_service(tmp_path, monkeypatch):
    """CorpusService with temporary state file."""
    state_path = tmp_path / 'corpus_state.json'
    monkeypatch.setattr('app.services.corpus_service.CORPUS_STATE_PATH', state_path)
    store = MagicMock()
    store.count.return_value = 0
    return CorpusService(store=store)


def test_register_document(corpus_service):
    corpus_service.register_document('sop-001', 'Incident Response', 'internal', 'sop_001.md')
    doc = corpus_service.get_document('sop-001')
    assert doc is not None
    assert doc['status'] == DocumentStatus.ACTIVE


def test_revoke_document(corpus_service):
    corpus_service.register_document('sop-001', 'Incident Response', 'internal', 'sop_001.md')
    assert corpus_service.revoke_document('sop-001', 'Outdated procedure') is True
    doc = corpus_service.get_document('sop-001')
    assert doc['status'] == DocumentStatus.REVOKED
    assert doc['revoked_reason'] == 'Outdated procedure'


def test_revoke_nonexistent_returns_false(corpus_service):
    assert corpus_service.revoke_document('nonexistent', 'reason') is False


def test_supersede_document(corpus_service):
    corpus_service.register_document('sop-001-v1', 'Incident Response v1', 'internal', 'sop_001.md')
    corpus_service.register_document('sop-001-v2', 'Incident Response v2', 'internal', 'sop_001_v2.md')
    assert corpus_service.supersede_document('sop-001-v1', 'sop-001-v2') is True
    old = corpus_service.get_document('sop-001-v1')
    assert old['status'] == DocumentStatus.SUPERSEDED
    assert old['superseded_by'] == 'sop-001-v2'


def test_list_documents_with_filter(corpus_service):
    corpus_service.register_document('d1', 'Doc 1', 'internal', 'd1.md')
    corpus_service.register_document('d2', 'Doc 2', 'internal', 'd2.md')
    corpus_service.revoke_document('d2', 'reason')

    active = corpus_service.list_documents(status_filter='active')
    assert len(active) == 1
    assert active[0]['doc_id'] == 'd1'


def test_corpus_status(corpus_service):
    corpus_service.register_document('d1', 'Doc 1', 'internal', 'd1.md')
    status = corpus_service.get_corpus_status()
    assert status['total_documents'] == 1
    assert 'active' in status['status_counts']


def test_ingestion_run_tracking(corpus_service):
    run_id = corpus_service.start_ingestion_run('/tmp/docs')
    assert run_id.startswith('run-')
    corpus_service.complete_ingestion_run(run_id, 5, 25, [])
    status = corpus_service.get_corpus_status()
    assert status['ingestion_runs'] == 1
    assert status['current_version'] is not None

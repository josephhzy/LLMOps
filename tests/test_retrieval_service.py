"""Retrieval service tests."""

from app.services.retrieval_service import RetrievalService


def test_acl_filter_admin_sees_all(sample_chunks):
    service = RetrievalService()
    filtered = service.apply_acl_filter(sample_chunks, 'admin')
    assert len(filtered) == 3  # Admin sees restricted chunks


def test_acl_filter_viewer_drops_restricted(sample_chunks):
    service = RetrievalService()
    filtered = service.apply_acl_filter(sample_chunks, 'viewer')
    assert len(filtered) == 2  # Viewer cannot see restricted
    assert all(c.metadata.get('classification') != 'restricted' for c in filtered)


def test_prepare_context_format(sample_chunks):
    service = RetrievalService()
    context = service.prepare_context(sample_chunks[:2])
    assert '[1]' in context
    assert '[2]' in context
    assert 'Incident Response SOP' in context


def test_prepare_context_empty():
    service = RetrievalService()
    context = service.prepare_context([])
    assert context == ''

"""Shared test fixtures and configuration."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api.main import create_app
from app.models.domain import RetrievedChunk


@pytest.fixture
def client():
    """Shared test client fixture."""
    return TestClient(create_app())


@pytest.fixture
def sample_chunks():
    """Realistic RetrievedChunk instances for unit tests."""
    return [
        RetrievedChunk(
            doc_id='sop-001',
            chunk_id='sop-001-c001',
            title='Incident Response SOP',
            content='The first step in incident response is to triage the event and classify its severity level from P1 to P4.',
            score=0.91,
            metadata={'classification': 'internal', 'document_status': 'active'},
        ),
        RetrievedChunk(
            doc_id='sop-001',
            chunk_id='sop-001-c002',
            title='Incident Response SOP',
            content='After triage, the analyst must notify the duty officer within 15 minutes for P1 incidents.',
            score=0.78,
            metadata={'classification': 'internal', 'document_status': 'active'},
        ),
        RetrievedChunk(
            doc_id='sop-003',
            chunk_id='sop-003-c001',
            title='Access Control Policy',
            content='All access requests must be approved by the system owner and reviewed quarterly.',
            score=0.45,
            metadata={'classification': 'restricted', 'document_status': 'active'},
        ),
    ]


@pytest.fixture
def sample_evidence_text():
    """Sample evidence block as it would appear in a rendered prompt."""
    return (
        '[1] Incident Response SOP\n'
        'The first step in incident response is to triage the event and classify its severity level.\n\n'
        '[2] Incident Response SOP\n'
        'After triage, the analyst must notify the duty officer within 15 minutes for P1 incidents.'
    )

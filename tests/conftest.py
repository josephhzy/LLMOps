"""Shared test fixtures and configuration."""

from __future__ import annotations

import hashlib

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.api.main import create_app
from app.models.domain import RetrievedChunk

_EMBED_DIM = 384


class _OfflineEmbedder:
    """Deterministic offline stand-in for SentenceTransformer.

    Hashing bag-of-words: texts that share tokens get a high cosine similarity,
    so lexical retrieval behaviour is preserved for unit tests with no network
    call or model download (CI runners get HuggingFace-rate-limited).
    """

    def _vec(self, text):
        v = np.zeros(_EMBED_DIM, dtype='float32')
        for tok in str(text).lower().split():
            v[int(hashlib.md5(tok.encode(), usedforsecurity=False).hexdigest(), 16) % _EMBED_DIM] += 1.0
        norm = float(np.linalg.norm(v))
        return v / norm if norm else v

    def encode(self, texts, show_progress_bar=False, convert_to_numpy=True, **kwargs):
        single = isinstance(texts, str)
        arr = np.array([self._vec(t) for t in ([texts] if single else list(texts))], dtype='float32')
        return arr[0] if single else arr


class _OfflineCrossEncoder:
    """Offline reranker stand-in: token-overlap score keeps reranking order sensible."""

    def predict(self, pairs, **kwargs):
        scores = []
        for query, passage in pairs:
            q = set(str(query).lower().split())
            p = set(str(passage).lower().split())
            scores.append(len(q & p) / (len(q) + 1e-9))
        return np.array(scores, dtype='float32')


@pytest.fixture(autouse=True)
def _offline_models():
    """Inject deterministic offline models so unit tests never download from HuggingFace."""
    from app.services import embedding_service, reranker_service

    embedding_service._model_cache[embedding_service.settings.embedding_model] = _OfflineEmbedder()
    reranker_service._cross_encoder_cache[reranker_service.settings.cross_encoder_model] = _OfflineCrossEncoder()
    yield
    embedding_service._model_cache.pop(embedding_service.settings.embedding_model, None)
    reranker_service._cross_encoder_cache.pop(reranker_service.settings.cross_encoder_model, None)


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

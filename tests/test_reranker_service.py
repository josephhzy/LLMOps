"""Reranker service tests."""

import pytest

from app.models.domain import RetrievedChunk
from app.services.reranker_service import RerankerService


@pytest.fixture
def reranker():
    return RerankerService()


@pytest.fixture
def diverse_chunks():
    return [
        RetrievedChunk(
            doc_id='d1',
            chunk_id='c1',
            title='Incident Response',
            content='The incident response procedure involves triage, classification, and escalation.',
            score=0.5,
            metadata={},
        ),
        RetrievedChunk(
            doc_id='d2',
            chunk_id='c2',
            title='Access Control',
            content='Access control policies govern user permissions and authentication requirements.',
            score=0.8,
            metadata={},
        ),
        RetrievedChunk(
            doc_id='d3',
            chunk_id='c3',
            title='Change Management',
            content='Change management requires CAB approval and rollback planning.',
            score=0.3,
            metadata={},
        ),
    ]


@pytest.mark.asyncio
async def test_tfidf_reranker_returns_all_chunks(reranker, diverse_chunks):
    result = await reranker.rerank('incident response procedure', diverse_chunks)
    assert len(result) == 3


@pytest.mark.asyncio
async def test_tfidf_reranker_boosts_relevant(reranker, diverse_chunks):
    result = await reranker.rerank('incident response triage', diverse_chunks)
    # The incident response chunk should be ranked higher after reranking
    assert result[0].doc_id == 'd1'


@pytest.mark.asyncio
async def test_reranker_empty_chunks(reranker):
    result = await reranker.rerank('test query', [])
    assert result == []


@pytest.mark.asyncio
async def test_reranker_single_chunk(reranker):
    chunk = RetrievedChunk(
        doc_id='d1',
        chunk_id='c1',
        title='Test',
        content='Test content',
        score=0.5,
        metadata={},
    )
    result = await reranker.rerank('test', [chunk])
    assert len(result) == 1

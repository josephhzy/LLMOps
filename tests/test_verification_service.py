"""Verification service tests."""

from app.models.domain import RetrievedChunk
from app.services.verification_service import VerificationService


def _make_chunk(content: str) -> RetrievedChunk:
    return RetrievedChunk(
        doc_id='d1',
        chunk_id='c1',
        title='Test',
        content=content,
        score=0.9,
        metadata={},
    )


def test_verify_no_chunks_returns_zero():
    service = VerificationService()
    result = service.verify_grounding('Some answer text here.', [])
    assert result['supported_ratio'] == 0.0
    assert result['num_claims'] == 0


def test_verify_empty_answer():
    service = VerificationService()
    chunks = [_make_chunk('Evidence content here.')]
    result = service.verify_grounding('', chunks)
    assert result['supported_ratio'] == 0.0


def test_verify_supported_answer():
    service = VerificationService()
    chunks = [
        _make_chunk('The incident response procedure begins with triage and severity classification.'),
    ]
    answer = 'The incident response procedure begins with triage and severity classification.'
    result = service.verify_grounding(answer, chunks)
    assert result['supported_ratio'] > 0.5
    assert result['num_claims'] >= 1


def test_verify_unsupported_answer():
    service = VerificationService()
    chunks = [
        _make_chunk('The incident response procedure begins with triage and severity classification.'),
    ]
    answer = 'Quantum computing uses qubits to perform calculations exponentially faster than classical computers.'
    result = service.verify_grounding(answer, chunks)
    assert result['supported_ratio'] < 0.5


def test_verify_returns_sentence_verdicts():
    service = VerificationService()
    chunks = [_make_chunk('Access control requires quarterly reviews.')]
    answer = 'Access control requires quarterly reviews. The sun is a star.'
    result = service.verify_grounding(answer, chunks)
    assert 'sentence_verdicts' in result
    assert len(result['sentence_verdicts']) >= 1
    for verdict in result['sentence_verdicts']:
        assert 'sentence' in verdict
        assert 'max_similarity' in verdict
        assert 'supported' in verdict

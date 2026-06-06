"""NLI verifier tests.

Covers the lightweight surface (tokenisation, unavailable-model fallback,
empty-input guards) without requiring the ~180MB model download at test
time. A marker-gated integration test exercises a real forward pass when
the model is available; it is skipped by default.
"""

from __future__ import annotations

import pytest

from app.models.domain import RetrievedChunk
from app.verification.nli_verifier import NLIVerifier


def _chunk(content: str, doc_id: str = 'd1') -> RetrievedChunk:
    return RetrievedChunk(
        doc_id=doc_id,
        chunk_id=f'{doc_id}-c1',
        title='t',
        content=content,
        score=0.9,
        metadata={},
    )


def test_split_claims_filters_short_fragments():
    v = NLIVerifier.__new__(NLIVerifier)  # skip __init__
    claims = v._split_claims('Short. This is a longer sentence of claims. Ok.')
    # The two short fragments ('Short.', 'Ok.') are under 15 chars after strip.
    assert claims == ['This is a longer sentence of claims.']


def test_split_claims_strips_citation_markers():
    v = NLIVerifier.__new__(NLIVerifier)
    claims = v._split_claims('The procedure starts with triage [1]. Severity is classified [2].')
    assert len(claims) == 2
    assert '[1]' not in claims[0]
    assert '[2]' not in claims[1]


def test_unavailable_model_returns_sentinel(monkeypatch):
    """When the model can't be loaded, the verifier returns a clean
    sentinel dict with `verifier='nli_unavailable'` so callers can
    fall back instead of crashing."""
    v = NLIVerifier(model_name='definitely-not-a-real-model/does-not-exist')

    def _fail_load(self):
        self._load_error = 'forced failure'
        return False

    monkeypatch.setattr(NLIVerifier, '_load_model', _fail_load)

    result = v.verify_grounding('Some answer.', [_chunk('Some evidence.')])
    assert result['verifier'] == 'nli_unavailable'
    assert result['supported_ratio'] == 0.0
    assert result['error'] == 'forced failure'


def test_empty_answer_returns_zero(monkeypatch):
    v = NLIVerifier()
    # Pretend model is loaded so we don't trigger a download.
    monkeypatch.setattr(NLIVerifier, '_load_model', lambda self: True)
    v._model = object()
    result = v.verify_grounding('', [_chunk('evidence')])
    assert result['supported_ratio'] == 0.0
    assert result['num_claims'] == 0
    assert result['verifier'] == 'nli'


def test_no_chunks_returns_zero(monkeypatch):
    v = NLIVerifier()
    monkeypatch.setattr(NLIVerifier, '_load_model', lambda self: True)
    v._model = object()
    result = v.verify_grounding('This is a real answer sentence.', [])
    assert result['supported_ratio'] == 0.0
    assert result['num_claims'] == 0


def test_is_available_probes_load(monkeypatch):
    v = NLIVerifier()
    calls = {'n': 0}

    def _fake_load(self):
        calls['n'] += 1
        return True

    monkeypatch.setattr(NLIVerifier, '_load_model', _fake_load)
    assert v.is_available() is True
    assert calls['n'] == 1


@pytest.mark.integration
def test_forward_pass_integration():
    """Integration: real model, real forward pass. Skipped in the
    fast unit run. Run with `pytest -m integration`.
    """
    v = NLIVerifier()
    if not v.is_available():
        pytest.skip(f'NLI model unavailable: {v._load_error}')

    chunks = [
        _chunk(
            'The first step in incident response is to triage the event and classify its severity level from P1 to P4.'
        ),
    ]
    # Entailed answer — should land in 'entailment' for at least one claim.
    answer = 'Incident response begins with triage and severity classification.'
    result = v.verify_grounding(answer, chunks)
    assert result['verifier'] == 'nli'
    assert result['num_claims'] >= 1
    assert 'label_distribution' in result
    # Contradictory answer — should NOT be marked supported.
    bad = 'Incident response begins by ignoring all alerts and doing nothing.'
    bad_result = v.verify_grounding(bad, chunks)
    assert bad_result['verifier'] == 'nli'
    # Contradiction or neutral — not supported.
    assert bad_result['supported_ratio'] <= result['supported_ratio']

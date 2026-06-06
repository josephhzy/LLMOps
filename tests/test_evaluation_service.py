"""Evaluation service tests."""

from app.services.evaluation_service import EvaluationService


def test_check_promotion_gate_pass():
    service = EvaluationService()
    metrics = {'grounded_support': 0.85, 'citation_coverage': 0.80}
    thresholds = {'grounded_support': 0.75, 'citation_coverage': 0.70}
    assert service.check_promotion_gate(metrics, thresholds) is True


def test_check_promotion_gate_fail():
    service = EvaluationService()
    metrics = {'grounded_support': 0.60, 'citation_coverage': 0.80}
    thresholds = {'grounded_support': 0.75, 'citation_coverage': 0.70}
    assert service.check_promotion_gate(metrics, thresholds) is False


def test_compare_runs_improvement():
    service = EvaluationService()
    baseline = {'grounded_support': 0.70, 'citation_coverage': 0.65, 'hallucination_rate': 0.30}
    candidate = {'grounded_support': 0.85, 'citation_coverage': 0.80, 'hallucination_rate': 0.15}
    result = service.compare_runs(baseline, candidate)
    assert result['candidate_beats_baseline'] is True
    assert 'grounded_support' in result['improvements']
    assert len(result['regressions']) == 0


def test_compare_runs_regression():
    service = EvaluationService()
    baseline = {'grounded_support': 0.85, 'citation_coverage': 0.80, 'hallucination_rate': 0.15}
    candidate = {'grounded_support': 0.70, 'citation_coverage': 0.60, 'hallucination_rate': 0.30}
    result = service.compare_runs(baseline, candidate)
    assert result['candidate_beats_baseline'] is False
    assert len(result['regressions']) > 0

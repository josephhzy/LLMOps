"""Model registry tests."""

import pytest

from app.domain.models import ModelRegistryEntry, PromotionStatus
from app.services.model_registry import ModelRegistry


@pytest.fixture
def registry(tmp_path):
    return ModelRegistry(registry_path=tmp_path / 'registry.json')


def _make_entry(model_id: str = 'model-001') -> ModelRegistryEntry:
    return ModelRegistryEntry(
        model_id=model_id,
        backend='template',
        prompt_version='grounded_answer:v1',
        embedding_model='all-MiniLM-L6-v2',
    )


def test_register_model(registry):
    entry = _make_entry()
    model_id = registry.register(entry)
    assert model_id == 'model-001'
    history = registry.get_history()
    assert len(history) == 1
    assert history[0]['status'] == PromotionStatus.CANDIDATE


def test_promote_to_shadow(registry):
    registry.register(_make_entry())
    assert registry.promote('model-001', PromotionStatus.SHADOW) is True
    history = registry.get_history()
    assert history[0]['status'] == PromotionStatus.SHADOW


def test_promote_to_production_requires_eval(registry):
    registry.register(_make_entry())
    # Without eval metrics, promotion should fail
    assert registry.promote('model-001', PromotionStatus.PRODUCTION) is False
    history = registry.get_history()
    assert history[0]['status'] == PromotionStatus.REJECTED


def test_promote_to_production_with_passing_eval(registry):
    registry.register(_make_entry())
    eval_metrics = {'grounded_support': 0.85, 'citation_coverage': 0.80}
    assert registry.promote('model-001', PromotionStatus.PRODUCTION, eval_metrics) is True
    active = registry.get_active()
    assert active is not None
    assert active['model_id'] == 'model-001'


def test_promote_to_production_with_failing_eval(registry):
    registry.register(_make_entry())
    eval_metrics = {'grounded_support': 0.50, 'citation_coverage': 0.40}
    assert registry.promote('model-001', PromotionStatus.PRODUCTION, eval_metrics) is False


def test_get_active_no_production(registry):
    registry.register(_make_entry())
    assert registry.get_active() is None


def test_promote_demotes_current_production(registry):
    registry.register(_make_entry('model-001'))
    registry.register(_make_entry('model-002'))

    eval_good = {'grounded_support': 0.85, 'citation_coverage': 0.80}
    registry.promote('model-001', PromotionStatus.PRODUCTION, eval_good)
    registry.promote('model-002', PromotionStatus.PRODUCTION, eval_good)

    active = registry.get_active()
    assert active['model_id'] == 'model-002'


def test_promote_rolls_back_on_save_failure(registry, monkeypatch):
    registry.register(_make_entry('model-001'))
    registry.register(_make_entry('model-002'))

    eval_good = {'grounded_support': 0.85, 'citation_coverage': 0.80}
    registry.promote('model-001', PromotionStatus.PRODUCTION, eval_good)

    # model-001 is now PRODUCTION; simulate _save raising during model-002 promotion
    call_count = {'n': 0}
    original_save = registry._save

    def flaky_save():
        call_count['n'] += 1
        if call_count['n'] == 1:
            raise OSError('disk full')
        original_save()

    monkeypatch.setattr(registry, '_save', flaky_save)

    with pytest.raises(OSError):
        registry.promote('model-002', PromotionStatus.PRODUCTION, eval_good)

    # model-001 should be restored to PRODUCTION after rollback
    active = registry.get_active()
    assert active is not None
    assert active['model_id'] == 'model-001'
    assert active['status'] == PromotionStatus.PRODUCTION

"""Model registry — lightweight local model lifecycle tracking.

File-backed registry for tracking model bundles through promotion stages:
candidate -> shadow -> canary -> production (or rejected).

Promotion requires passing evaluation gate.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from app.core.audit import audit
from app.core.logging import get_logger
from app.domain.models import ModelRegistryEntry, PromotionStatus

logger = get_logger(__name__)

REGISTRY_PATH = Path('data/model_registry.json')


class ModelRegistry:
    """File-backed model registry with promotion gates."""

    def __init__(self, registry_path: Path | None = None) -> None:
        self.registry_path = registry_path or REGISTRY_PATH
        self._entries = self._load()

    def _load(self) -> list[dict]:
        if self.registry_path.exists():
            return json.loads(self.registry_path.read_text())
        return []

    def _save(self) -> None:
        self.registry_path.parent.mkdir(parents=True, exist_ok=True)
        self.registry_path.write_text(json.dumps(self._entries, indent=2))

    def register(self, entry: ModelRegistryEntry) -> str:
        """Register a new model bundle as candidate."""
        entry.status = PromotionStatus.CANDIDATE
        entry.registered_at = datetime.now(UTC).isoformat()
        self._entries.append(self._entry_to_dict(entry))
        self._save()
        logger.info('Model registered', model_id=entry.model_id, status=entry.status)
        return entry.model_id

    def promote(self, model_id: str, new_status: str, eval_metrics: dict | None = None) -> bool:
        """Promote a model to a new status. Requires eval gate for production promotion."""
        entry = self._find(model_id)
        if not entry:
            logger.warning('Cannot promote: model not found', model_id=model_id)
            return False

        # Enforce promotion gates
        if new_status == PromotionStatus.PRODUCTION:
            if not self._check_promotion_gate(eval_metrics):
                logger.warning('Promotion gate failed', model_id=model_id)
                entry['status'] = PromotionStatus.REJECTED
                entry['notes'] = 'Failed promotion gate'
                self._save()
                audit.log_event(
                    'model',
                    'system',
                    'promote',
                    target=model_id,
                    outcome='denied',
                    details={'reason': 'promotion_gate_failed'},
                )
                return False
            # Save old production model state before demotion for rollback
            old_production = self._get_current_production_snapshot()
            prev_entry = dict(entry)
            self._demote_current_production()

            # Attempt promotion; rollback demotion if something goes wrong
            try:
                entry['status'] = new_status
                entry['promoted_at'] = datetime.now(UTC).isoformat()
                if eval_metrics:
                    entry['eval_snapshot'] = eval_metrics
                self._save()
            except Exception:
                logger.error(
                    'Failed to promote model, rolling back demotion',
                    model_id=model_id,
                )
                # Revert the candidate's in-memory promotion too; otherwise both
                # the failed candidate and the restored model read as PRODUCTION.
                entry.clear()
                entry.update(prev_entry)
                self._rollback_production(old_production)
                raise

            audit.log_event(
                'model',
                'system',
                'promote',
                target=model_id,
                outcome='success',
                details={'new_status': new_status, 'eval_metrics': eval_metrics},
            )
            logger.info('Model promoted', model_id=model_id, new_status=new_status)
            return True

        entry['status'] = new_status
        entry['promoted_at'] = datetime.now(UTC).isoformat()
        if eval_metrics:
            entry['eval_snapshot'] = eval_metrics
        self._save()
        audit.log_event(
            'model',
            'system',
            'promote',
            target=model_id,
            outcome='success',
            details={'new_status': new_status},
        )
        logger.info('Model promoted', model_id=model_id, new_status=new_status)
        return True

    def reject(self, model_id: str, reason: str = '') -> bool:
        """Reject a model candidate."""
        entry = self._find(model_id)
        if not entry:
            return False
        entry['status'] = PromotionStatus.REJECTED
        entry['notes'] = reason
        self._save()
        return True

    def get_active(self) -> dict | None:
        """Get the current production model bundle."""
        for entry in reversed(self._entries):
            if entry['status'] == PromotionStatus.PRODUCTION:
                return entry
        return None

    def get_history(self) -> list[dict]:
        """Get full registry history."""
        return list(reversed(self._entries))

    def _find(self, model_id: str) -> dict | None:
        for entry in self._entries:
            if entry['model_id'] == model_id:
                return entry
        return None

    def _get_current_production_snapshot(self) -> list[tuple[int, str, str]]:
        """Capture index, status, and notes of all production entries for rollback."""
        snapshot = []
        for i, entry in enumerate(self._entries):
            if entry['status'] == PromotionStatus.PRODUCTION:
                snapshot.append((i, entry['status'], entry.get('notes', '')))
        return snapshot

    def _rollback_production(self, snapshot: list[tuple[int, str, str]]) -> None:
        """Restore previously demoted production entries from snapshot."""
        for idx, status, notes in snapshot:
            self._entries[idx]['status'] = status
            self._entries[idx]['notes'] = notes
        self._save()
        logger.info('Rolled back production demotion', restored_count=len(snapshot))

    def _demote_current_production(self) -> None:
        """Move current production model to candidate status."""
        for entry in self._entries:
            if entry['status'] == PromotionStatus.PRODUCTION:
                entry['status'] = PromotionStatus.CANDIDATE
                entry['notes'] = f'Demoted at {datetime.now(UTC).isoformat()}'

    def _check_promotion_gate(self, eval_metrics: dict | None) -> bool:
        """Check if evaluation metrics meet promotion thresholds."""
        if not eval_metrics:
            return False
        thresholds = {
            'grounded_support': 0.75,
            'citation_coverage': 0.70,
        }
        return all(eval_metrics.get(k, 0) >= v for k, v in thresholds.items())

    def _entry_to_dict(self, entry: ModelRegistryEntry) -> dict:
        return {
            'model_id': entry.model_id,
            'backend': entry.backend,
            'prompt_version': entry.prompt_version,
            'embedding_model': entry.embedding_model,
            'eval_snapshot': entry.eval_snapshot,
            'status': entry.status,
            'registered_at': entry.registered_at,
            'promoted_at': entry.promoted_at,
            'notes': entry.notes,
        }

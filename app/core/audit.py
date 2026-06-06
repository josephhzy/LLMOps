"""Audit logging — append-only event trail.

Records security-relevant events: policy decisions, access attempts,
admin operations, document lifecycle changes.

File-backed for demo portability. Interface supports migration to
immutable log stores (Elasticsearch, S3, append-only DB table).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from app.core.logging import get_logger

logger = get_logger(__name__)

AUDIT_LOG_PATH = Path('data/audit.jsonl')


class AuditLogger:
    """Append-only audit event logger."""

    def __init__(self, log_path: Path | None = None) -> None:
        self.log_path = log_path or AUDIT_LOG_PATH
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def log_event(
        self,
        event_type: str,
        actor: str,
        action: str,
        target: str = '',
        outcome: str = 'success',
        details: dict | None = None,
    ) -> None:
        """Record an audit event.

        Args:
            event_type: Category (policy, access, admin, corpus, model).
            actor: Who performed the action (user_id, system, evaluator).
            action: What was done (query, revoke, promote, login).
            target: What was acted upon (doc_id, model_id, endpoint).
            outcome: Result (success, denied, failed).
            details: Additional context.
        """
        event = {
            'timestamp': datetime.now(UTC).isoformat(),
            'event_type': event_type,
            'actor': actor,
            'action': action,
            'target': target,
            'outcome': outcome,
            'details': details or {},
        }

        # Append to JSONL file (one JSON object per line)
        with open(self.log_path, 'a', encoding='utf-8') as f:
            f.write(json.dumps(event) + '\n')

        logger.debug('Audit event: %s/%s by %s -> %s', event_type, action, actor, outcome)

    def get_recent_events(self, limit: int = 50, event_type: str | None = None) -> list[dict]:
        """Read recent audit events.

        Intended for a future admin dashboard endpoint (e.g. GET /v1/admin/audit).
        Not currently wired to any route; available for direct use in debugging.
        """
        if not self.log_path.exists():
            return []

        events = []
        for line in self.log_path.read_text().strip().split('\n'):
            if not line:
                continue
            try:
                event = json.loads(line)
                if event_type is None or event.get('event_type') == event_type:
                    events.append(event)
            except json.JSONDecodeError:
                continue

        # Return most recent first
        return list(reversed(events[-limit:]))


# Module-level singleton
audit = AuditLogger()

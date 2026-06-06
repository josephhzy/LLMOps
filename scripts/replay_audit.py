"""Reconstruct what happened to a query from the audit log.

Usage:
    python scripts/replay_audit.py --trace-id trace-<hex>
    python scripts/replay_audit.py --query-id trace-<hex>   # alias
    python scripts/replay_audit.py --last 10                # replay the last N queries
    python scripts/replay_audit.py --since 2026-04-16T00:00:00+00:00

What this script can reconstruct (strictly from data/audit.jsonl):
    - The timestamp of the query event (from the `query` start event)
    - The authenticated user_id the query ran as
    - The declared question length (characters, not the text itself)
    - The retrieved chunk IDs and doc IDs (from the `query_result` event)
    - The model / prompt / policy / retriever versions used
    - The token counts, supported_ratio, confidence, and final policy action
    - A 16-char SHA-256 prefix of the answer (so the same answer can be
      correlated across runs without exposing its text)
    - Any corpus revocation events that happened in the same window
    - Any model promotion/rejection events in the same window

What this script deliberately does NOT reconstruct from the audit log:
    - The raw question text (audit logs only `question_length` by design,
      to keep the trail free of raw user input PII)
    - The raw answer text (only a truncated hash is logged — same reason)

If you need the raw text, pair the trace_id with a separate,
access-controlled store. The audit trail is designed to be sharable with
auditors who should NOT see user content.

Events consumed:
    - `query` — pipeline entry, carries question_length and trace_id
    - `query_result` — pipeline exit, carries the full replay payload
      (retrieved_chunk_ids, versions, ratios, actions, answer_hash).
      Emitted from RAGService.answer; see app/services/rag_service.py.
    - `policy` / `block_injection` — injection pre-checks.
    - `corpus` / `revoke_document` — revocations during the window.
    - `model` / `promote` — registry changes during the window.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

DEFAULT_AUDIT_PATH = Path('data/audit.jsonl')


@dataclass
class AuditEvent:
    timestamp: str
    event_type: str
    actor: str
    action: str
    target: str
    outcome: str
    details: dict = field(default_factory=dict)

    @property
    def trace_id(self) -> str | None:
        return self.details.get('trace_id') if isinstance(self.details, dict) else None


def load_events(path: Path) -> list[AuditEvent]:
    if not path.exists():
        return []
    events: list[AuditEvent] = []
    for line in path.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            raw = json.loads(line)
            events.append(
                AuditEvent(
                    timestamp=raw.get('timestamp', ''),
                    event_type=raw.get('event_type', ''),
                    actor=raw.get('actor', ''),
                    action=raw.get('action', ''),
                    target=raw.get('target', ''),
                    outcome=raw.get('outcome', 'unknown'),
                    details=raw.get('details') or {},
                )
            )
        except json.JSONDecodeError:
            continue
    return events


def by_trace_id(events: Iterable[AuditEvent], trace_id: str) -> list[AuditEvent]:
    return [e for e in events if e.trace_id == trace_id]


def last_n_queries(events: Iterable[AuditEvent], n: int) -> list[AuditEvent]:
    """Return the last N query-start events."""
    queries = [e for e in events if e.event_type == 'query' and e.action == 'query']
    return queries[-n:]


def since(events: Iterable[AuditEvent], cutoff: datetime) -> list[AuditEvent]:
    result = []
    for e in events:
        try:
            ts = datetime.fromisoformat(e.timestamp)
        except ValueError:
            continue
        if ts >= cutoff:
            result.append(e)
    return result


def reconstruct(events: list[AuditEvent], trace_id: str) -> dict:
    """Build what we can reconstruct for a single trace_id.

    Combines the `query` start event and the `query_result` end event
    (emitted by RAGService.answer) to produce a complete record of the
    request, minus the raw question/answer text — those are held out of
    the audit log on purpose (PII). If the `query_result` event is not
    present (e.g. the request blew up before the pipeline finished), we
    report the start event alone and flag the gap.
    """
    matched = by_trace_id(events, trace_id)

    query_start = next(
        (e for e in matched if e.event_type == 'query' and e.action == 'query'),
        None,
    )
    query_result = next(
        (e for e in matched if e.event_type == 'query_result'),
        None,
    )

    # Blocks recorded for this trace — NB `block_injection` itself does not
    # currently carry a trace_id in details (fires before the trace_id is
    # bound into the audit record), so most pre-check blocks will NOT be
    # here. Injection blocks that happened mid-request-flow would be.
    blocks = [e for e in matched if e.event_type == 'policy']

    reconstructible = query_start is not None and query_result is not None

    return {
        'trace_id': trace_id,
        'reconstructible': reconstructible,
        'query_event': {
            'timestamp': query_start.timestamp,
            'actor': query_start.actor,
            'outcome': query_start.outcome,
            'details': query_start.details,
        }
        if query_start
        else None,
        'query_result': {
            'timestamp': query_result.timestamp,
            'actor': query_result.actor,
            'outcome': query_result.outcome,
            'retrieved_chunk_ids': query_result.details.get('retrieved_chunk_ids', []),
            'retrieved_doc_ids': query_result.details.get('retrieved_doc_ids', []),
            'model_version': query_result.details.get('model_version'),
            'prompt_version': query_result.details.get('prompt_version'),
            'policy_version': query_result.details.get('policy_version'),
            'retriever_version': query_result.details.get('retriever_version'),
            'tokens_in': query_result.details.get('tokens_in'),
            'tokens_out': query_result.details.get('tokens_out'),
            'supported_ratio': query_result.details.get('supported_ratio'),
            'policy_action': query_result.details.get('policy_action'),
            'confidence': query_result.details.get('confidence'),
            'answer_hash': query_result.details.get('answer_hash'),
            'answer_length': query_result.details.get('answer_length'),
            'citation_count': query_result.details.get('citation_count'),
        }
        if query_result
        else None,
        'associated_policy_events': [
            {'timestamp': b.timestamp, 'action': b.action, 'outcome': b.outcome} for b in blocks
        ],
        'held_out_of_audit_by_design': [
            'Raw question text (question_length only is logged).',
            'Raw answer text (answer_hash + answer_length only are logged).',
        ],
        'note': (
            'When query_result is missing for a trace_id that has a query '
            'start event, the request did not reach the end of the pipeline. '
            'Check for a PolicyViolationError (injection) or a 5xx on that '
            'trace_id in the application logs.'
        )
        if query_start and not query_result
        else None,
    }


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog='replay_audit',
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        '--audit-path',
        type=Path,
        default=DEFAULT_AUDIT_PATH,
        help=f'Path to the audit JSONL file (default: {DEFAULT_AUDIT_PATH})',
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--trace-id', help='Reconstruct a single query by its trace_id')
    group.add_argument('--query-id', help='Alias for --trace-id')
    group.add_argument('--last', type=int, help='Replay the last N queries (summary only)')
    group.add_argument('--since', help='ISO timestamp; list all query events at or after this time')
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    events = load_events(args.audit_path)

    if not events:
        print(f'No audit events found at {args.audit_path}', file=sys.stderr)
        return 2

    trace_id = args.trace_id or args.query_id
    if trace_id:
        result = reconstruct(events, trace_id)
        print(json.dumps(result, indent=2))
        return 0 if result['reconstructible'] else 1

    if args.last is not None:
        queries = last_n_queries(events, args.last)
        print(
            json.dumps(
                [
                    {
                        'timestamp': q.timestamp,
                        'actor': q.actor,
                        'trace_id': q.trace_id,
                        'details': q.details,
                    }
                    for q in queries
                ],
                indent=2,
            )
        )
        return 0

    if args.since is not None:
        cutoff = datetime.fromisoformat(args.since)
        recent = since(events, cutoff)
        print(
            json.dumps(
                [
                    {
                        'timestamp': e.timestamp,
                        'event_type': e.event_type,
                        'action': e.action,
                        'actor': e.actor,
                        'target': e.target,
                        'outcome': e.outcome,
                        'details': e.details,
                    }
                    for e in recent
                ],
                indent=2,
            )
        )
        return 0

    return 0


if __name__ == '__main__':
    raise SystemExit(main())

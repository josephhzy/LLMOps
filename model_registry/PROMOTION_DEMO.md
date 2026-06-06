# Promotion gate demonstration

## What this proves

The promotion gate in `app/services/model_registry.py::ModelRegistry._check_promotion_gate` is not a decoration. A candidate that does not clear both thresholds is refused `production` status, moved to `rejected`, and the refusal is audit-logged.

Thresholds (hard-coded in `_check_promotion_gate`):

```
grounded_support    >= 0.75
citation_coverage   >= 0.70
```

Both must be present and at or above threshold. A missing metric counts as zero.

## Reproducible demo

```bash
python scripts/promotion_gate_demo.py
```

The audit log defaults to `data/audit.jsonl`; use `--audit-path /tmp/demo_audit.jsonl` for a throwaway run, matching the `--registry` flag for the registry file.

The script registers two candidates back-to-back:

| Candidate | `grounded_support` | `citation_coverage` | Expected outcome |
|-----------|-------------------|---------------------|-------------------|
| `promotion-demo-weak` | 0.62 | 0.55 | **Refused** (both metrics below threshold) |
| `promotion-demo-strong` | 0.82 | 0.78 | **Promoted to production** |

Sample output (elided for readability):

```
{
  "weak_candidate": {
    "model_id": "promotion-demo-weak",
    "submitted_metrics": {"grounded_support": 0.62, "citation_coverage": 0.55},
    "gate_passed": false,
    "final_status": "rejected",
    "notes": "Failed promotion gate"
  },
  "strong_candidate": {
    "model_id": "promotion-demo-strong",
    "submitted_metrics": {"grounded_support": 0.82, "citation_coverage": 0.78},
    "gate_passed": true,
    "final_status": "production"
  },
  "gate_thresholds": {
    "grounded_support": 0.75,
    "citation_coverage": 0.70
  }
}
```

## What the audit log records

When the weak candidate is refused, the registry writes to `data/audit.jsonl`:

```json
{
  "timestamp": "2026-...",
  "event_type": "model",
  "actor": "system",
  "action": "promote",
  "target": "promotion-demo-weak",
  "outcome": "denied",
  "details": {"reason": "promotion_gate_failed"}
}
```

When the strong candidate is accepted, the audit event looks like:

```json
{
  "timestamp": "2026-...",
  "event_type": "model",
  "actor": "system",
  "action": "promote",
  "target": "promotion-demo-strong",
  "outcome": "success",
  "details": {
    "new_status": "production",
    "eval_metrics": {"grounded_support": 0.82, "citation_coverage": 0.78}
  }
}
```

Both events are in the same append-only file. Anyone verifying the gate behaviour can run `grep 'promotion-demo' data/audit.jsonl` after running the demo — this returns exactly the two relevant audit entries. Alternatively, `python scripts/promotion_gate_demo.py` prints both entries directly to stdout so no grep is needed.

## Edge cases the gate handles

| Input | Result | Why |
|-------|--------|-----|
| `eval_metrics=None` | Refused | `_check_promotion_gate` returns `False` immediately |
| `eval_metrics={"grounded_support": 0.80}` only | Refused | `citation_coverage` missing → treated as 0 → below threshold |
| `eval_metrics={"grounded_support": 0.75, "citation_coverage": 0.70}` | Promoted | Boundary is inclusive (`>=`) |
| Promoting to `shadow` or `canary` with no metrics | Allowed | Gate only applies to `production` status (intentional — shadow traffic is how you measure a candidate in the first place) |

## What this does not prove

- The gate itself is enforced. The *quality* of the metrics it gates on is only as good as the evaluation pipeline (`pipelines/run_evaluation.py`) and the golden QA set. If golden QA is too easy, the gate lets bad models through; if too hard, it blocks good ones. See `evaluation/GOLDEN_QA_SPEC.md`.
- Rollback is wired in `promote()` (the previous production entry is snapshotted before demotion, and restored if the new promotion fails). The demo does not currently exercise a crash-mid-promotion, but the code path exists in `ModelRegistry._rollback_production`.

## How to demonstrate

"Show me a blocked promotion" — run the demo live, tail the audit log in another pane. The whole thing takes under 10 seconds and the artefact is a real JSON-L line, not a slide.

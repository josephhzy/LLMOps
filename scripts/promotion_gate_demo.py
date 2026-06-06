"""Promotion gate demonstration.

Reproduces the scenario where a candidate model with below-threshold
evaluation metrics attempts a production promotion and is blocked.

Expected flow:
    1. Register candidate `promotion-demo-weak` with synthetic below-threshold
       eval metrics: grounded_support=0.62, citation_coverage=0.55.
    2. Attempt to promote to `production` with those metrics.
    3. Gate refuses (grounded_support < 0.75 and citation_coverage < 0.70).
    4. Candidate is moved to `rejected`.
    5. An audit event is written with outcome='denied' and reason='promotion_gate_failed'.
    6. Registering a second candidate `promotion-demo-strong` with
       grounded_support=0.82, citation_coverage=0.78 DOES pass the gate
       and reaches production.

Run:
    python scripts/promotion_gate_demo.py

Output:
    Step-by-step log + a JSON summary at the end.

Cleanup:
    The demo writes to the registry at `data/model_registry.json`. If you
    want a throwaway run, set LLM_OPS_REGISTRY_PATH to a temp file before
    running (supported via the `--registry` argument).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.domain.models import ModelRegistryEntry, PromotionStatus
from app.services.model_registry import ModelRegistry


def run_demo(registry_path: Path | None = None) -> dict:
    registry = ModelRegistry(registry_path=registry_path)

    # --- Step 1: register the weak candidate ---
    weak_id = 'promotion-demo-weak'
    weak_entry = ModelRegistryEntry(
        model_id=weak_id,
        backend='template',
        prompt_version='grounded_answer:v1',
        embedding_model='all-MiniLM-L6-v2',
        notes='Synthetic below-threshold eval for gate demo',
    )
    registry.register(weak_entry)
    weak_metrics = {'grounded_support': 0.62, 'citation_coverage': 0.55}

    # --- Step 2: attempt promotion; expect rejection ---
    weak_promoted = registry.promote(
        model_id=weak_id,
        new_status=PromotionStatus.PRODUCTION,
        eval_metrics=weak_metrics,
    )

    # --- Step 3: register a passing candidate ---
    strong_id = 'promotion-demo-strong'
    strong_entry = ModelRegistryEntry(
        model_id=strong_id,
        backend='template',
        prompt_version='grounded_answer:v1',
        embedding_model='all-MiniLM-L6-v2',
        notes='Synthetic above-threshold eval for gate demo',
    )
    registry.register(strong_entry)
    strong_metrics = {'grounded_support': 0.82, 'citation_coverage': 0.78}

    # --- Step 4: promote the strong candidate ---
    strong_promoted = registry.promote(
        model_id=strong_id,
        new_status=PromotionStatus.PRODUCTION,
        eval_metrics=strong_metrics,
    )

    history = registry.get_history()
    weak_final = next(h for h in history if h['model_id'] == weak_id)
    strong_final = next(h for h in history if h['model_id'] == strong_id)

    return {
        'weak_candidate': {
            'model_id': weak_id,
            'submitted_metrics': weak_metrics,
            'gate_passed': weak_promoted,
            'final_status': weak_final['status'],
            'notes': weak_final.get('notes', ''),
        },
        'strong_candidate': {
            'model_id': strong_id,
            'submitted_metrics': strong_metrics,
            'gate_passed': strong_promoted,
            'final_status': strong_final['status'],
        },
        'gate_thresholds': {
            'grounded_support': 0.75,
            'citation_coverage': 0.70,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '--registry',
        type=Path,
        default=None,
        help='Path to a registry JSON file (default: data/model_registry.json)',
    )
    args = parser.parse_args()

    result = run_demo(registry_path=args.registry)
    print(json.dumps(result, indent=2))

    # Exit 0 if the demo matched expectations (weak rejected, strong promoted),
    # non-zero otherwise so CI can catch a regression in the gate logic.
    weak_rejected = (
        not result['weak_candidate']['gate_passed']
        and result['weak_candidate']['final_status'] == PromotionStatus.REJECTED
    )
    strong_promoted = (
        result['strong_candidate']['gate_passed']
        and result['strong_candidate']['final_status'] == PromotionStatus.PRODUCTION
    )
    return 0 if (weak_rejected and strong_promoted) else 1


if __name__ == '__main__':
    raise SystemExit(main())

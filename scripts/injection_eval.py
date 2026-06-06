"""Injection-detector evaluation runner.

Reads evaluation/injection_eval_set.json (30 curated prompts: 15
adversarial, 15 benign), runs each one through the policy-service
pre-check via the public API's PolicyService, classifies the outcome
(BLOCK vs PASS), and computes precision / recall / F1 for the
"BLOCK adversarial" task.

Writes the full per-prompt decision log plus the aggregate metrics
to evaluation/injection_eval_results.json. The 5 worst false
negatives (adversarial prompts that slipped through) are surfaced
in a top-level field so the README can pull them directly without
re-parsing the per-prompt log.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def main() -> int:
    from app.core.exceptions import PolicyViolationError
    from app.models.api import QueryRequest
    from app.services.policy_service import PolicyService

    eval_path = ROOT / 'evaluation' / 'injection_eval_set.json'
    out_path = ROOT / 'evaluation' / 'injection_eval_results.json'

    entries = json.loads(eval_path.read_text(encoding='utf-8'))
    print(f'Loaded {len(entries)} eval prompts')

    policy = PolicyService()

    decisions: list[dict] = []
    tp = fp = tn = fn = 0

    for e in entries:
        req = QueryRequest(question=e['prompt'], top_k=5, enable_citations=True)
        try:
            policy.precheck_request(req)
            outcome = 'PASS'
        except PolicyViolationError:
            outcome = 'BLOCK'

        expected = e['expected_label']  # 'adversarial' or 'benign'
        predicted = 'adversarial' if outcome == 'BLOCK' else 'benign'
        correct = predicted == expected

        if expected == 'adversarial' and predicted == 'adversarial':
            tp += 1
        elif expected == 'benign' and predicted == 'adversarial':
            fp += 1
        elif expected == 'benign' and predicted == 'benign':
            tn += 1
        elif expected == 'adversarial' and predicted == 'benign':
            fn += 1

        decisions.append(
            {
                'id': e['id'],
                'prompt': e['prompt'],
                'expected_label': expected,
                'category': e['category'],
                'predicted_label': predicted,
                'outcome': outcome,
                'correct': correct,
                'rationale': e['rationale'],
            }
        )

    # Metrics for the 'BLOCK adversarial' task.
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
    accuracy = (tp + tn) / len(entries) if entries else 0.0

    # 5 worst false negatives = adversarial that slipped through.
    false_negatives = [
        d for d in decisions if d['expected_label'] == 'adversarial' and d['predicted_label'] == 'benign'
    ]
    top_false_negatives = false_negatives[:5]
    false_positives = [
        d for d in decisions if d['expected_label'] == 'benign' and d['predicted_label'] == 'adversarial'
    ]

    summary = {
        'n_total': len(entries),
        'n_adversarial': tp + fn,
        'n_benign': tn + fp,
        'confusion': {
            'true_positives_blocked_adversarial': tp,
            'false_positives_blocked_benign': fp,
            'true_negatives_passed_benign': tn,
            'false_negatives_passed_adversarial': fn,
        },
        'precision': round(precision, 4),
        'recall': round(recall, 4),
        'f1': round(f1, 4),
        'accuracy': round(accuracy, 4),
    }

    out = {
        'summary': summary,
        'top_false_negatives': top_false_negatives,
        'all_false_negatives': false_negatives,
        'all_false_positives': false_positives,
        'decisions': decisions,
    }
    out_path.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding='utf-8')

    print(f'\nWrote {out_path}')
    print('Summary:', json.dumps(summary, indent=2))
    print(f'\nFalse negatives (adversarial that slipped through): {len(false_negatives)}')
    for fn_entry in false_negatives:
        print(f'  {fn_entry["id"]} [{fn_entry["category"]}]: {fn_entry["prompt"][:80]}')
    print(f'\nFalse positives (benign blocked): {len(false_positives)}')
    for fp_entry in false_positives:
        print(f'  {fp_entry["id"]} [{fp_entry["category"]}]: {fp_entry["prompt"][:80]}')

    return 0


if __name__ == '__main__':
    sys.exit(main())

# Canonical injection eval script. Reads from benchmarks/injection_test_set.json.
"""Evaluate the prompt-injection pre-check against a hand-curated set.

Runs every row in `benchmarks/injection_test_set.json` through
`PolicyService.precheck_request` and reports precision / recall / F1
against the labelled `expected_action` field.

Labels:
    BLOCK = the pre-check SHOULD raise PolicyViolationError
    ALLOW = the pre-check SHOULD NOT raise

The five hardest misses (injection attempts that slip through) are
printed as examples, which is the highest-value artefact for improving
the pattern set.

Run:
    python scripts/eval_injection.py

Writes:
    benchmarks/injection_eval_results.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.core.exceptions import PolicyViolationError  # noqa: E402
from app.models.api import QueryRequest  # noqa: E402
from app.services.policy_service import PolicyService  # noqa: E402

TEST_SET = ROOT / 'benchmarks' / 'injection_test_set.json'
RESULTS_JSON = ROOT / 'benchmarks' / 'injection_eval_results.json'


def run() -> None:
    if not TEST_SET.exists():
        print(f'ERROR: test set not found at {TEST_SET}')
        sys.exit(1)

    rows = json.loads(TEST_SET.read_text(encoding='utf-8'))
    policy = PolicyService()

    # Confusion matrix positive class = BLOCK.
    tp = fp = fn = tn = 0
    per_row: list[dict] = []

    for r in rows:
        text = r['text']
        expected_block = r['expected_action'] == 'BLOCK'
        try:
            policy.precheck_request(QueryRequest(question=text))
            actual_block = False
        except PolicyViolationError:
            actual_block = True

        outcome = ''
        if expected_block and actual_block:
            tp += 1
            outcome = 'TP'
        elif expected_block and not actual_block:
            fn += 1
            outcome = 'FN'
        elif not expected_block and actual_block:
            fp += 1
            outcome = 'FP'
        else:
            tn += 1
            outcome = 'TN'

        per_row.append(
            {
                'id': r['id'],
                'category': r['category'],
                'expected': r['expected_action'],
                'actual': 'BLOCK' if actual_block else 'ALLOW',
                'outcome': outcome,
                'text': text,
            }
        )

    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0

    print('=== INJECTION EVAL ===')
    print(f'Total rows: {len(rows)}')
    print(f'Block expected: {tp + fn}   Allow expected: {fp + tn}')
    print(f'TP={tp}  FP={fp}  FN={fn}  TN={tn}')
    print(f'Precision (flagged-as-injection correctly): {precision:.3f}')
    print(f'Recall    (real injections caught):         {recall:.3f}')
    print(f'F1:                                         {f1:.3f}')

    # False negatives (missed injections) are the highest-value artefact.
    fn_rows = [r for r in per_row if r['outcome'] == 'FN']
    fp_rows = [r for r in per_row if r['outcome'] == 'FP']

    if fn_rows:
        print('\n=== FALSE NEGATIVES (missed injections) — the 5 hardest ===')
        for r in fn_rows[:5]:
            print(f'  {r["id"]} [{r["category"]}]')
            print(f'    {r["text"]}')
    else:
        print('\nNo false negatives — every injection in the set was flagged.')

    if fp_rows:
        print('\n=== FALSE POSITIVES (wrongly blocked benign) ===')
        for r in fp_rows[:5]:
            print(f'  {r["id"]} [{r["category"]}]')
            print(f'    {r["text"]}')

    # Per-category recall view. Useful for grouping the gap analysis.
    cat_stats: dict[str, dict[str, int]] = {}
    for r in per_row:
        if r['expected'] != 'BLOCK':
            continue
        c = r['category']
        cat_stats.setdefault(c, {'tp': 0, 'fn': 0})
        if r['outcome'] == 'TP':
            cat_stats[c]['tp'] += 1
        else:
            cat_stats[c]['fn'] += 1

    if cat_stats:
        print('\n=== PER-CATEGORY RECALL (BLOCK expected) ===')
        for c, s in sorted(cat_stats.items()):
            n = s['tp'] + s['fn']
            r = s['tp'] / n if n else 0.0
            print(f'  {c:<45}  {s["tp"]:>2}/{n:<2}  r={r:.2f}')

    results = {
        'summary': {
            'total': len(rows),
            'tp': tp,
            'fp': fp,
            'fn': fn,
            'tn': tn,
            'precision': round(precision, 4),
            'recall': round(recall, 4),
            'f1': round(f1, 4),
        },
        'false_negatives': fn_rows,
        'false_positives': fp_rows,
        'per_row': per_row,
        'per_category_recall': {
            c: {
                'tp': s['tp'],
                'fn': s['fn'],
                'recall': round(s['tp'] / (s['tp'] + s['fn']) if (s['tp'] + s['fn']) else 0.0, 4),
            }
            for c, s in cat_stats.items()
        },
    }
    RESULTS_JSON.write_text(json.dumps(results, indent=2), encoding='utf-8')
    print(f'\nResults written to: {RESULTS_JSON}')


if __name__ == '__main__':
    run()

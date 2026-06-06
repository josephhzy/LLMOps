"""Evaluation pipeline.

Runs a golden QA benchmark against the current RAG configuration,
compares against saved baseline, and checks promotion gates.
Saves candidate as new baseline on gate pass.

Run: python -m pipelines.run_evaluation
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path

from app.services.evaluation_service import EvaluationService

logger = logging.getLogger(__name__)

THRESHOLDS = {
    'grounded_support': 0.75,
    'citation_coverage': 0.70,
}

BASELINE_PATH = Path(__file__).resolve().parent.parent / 'data' / 'baselines' / 'latest.json'


def main() -> dict:
    """Run evaluation pipeline."""
    service = EvaluationService()

    # Run benchmark
    candidate = service.run_benchmark('golden_qa_v1', f'bundle-{time.strftime("%Y%m%d")}')

    # Load or create baseline
    if BASELINE_PATH.exists():
        baseline = json.loads(BASELINE_PATH.read_text())
    else:
        baseline = {'grounded_support': 0.0, 'citation_coverage': 0.0}

    # Compare
    comparison = service.compare_runs(baseline, candidate)

    # Gate check
    gate_pass = service.check_promotion_gate(candidate, THRESHOLDS)

    result = {
        'candidate_metrics': candidate,
        'baseline_metrics': baseline,
        'comparison': comparison,
        'promotion_gate': 'PASS' if gate_pass else 'FAIL',
        'thresholds': THRESHOLDS,
    }

    # Save candidate as new baseline if it passes
    if gate_pass:
        BASELINE_PATH.parent.mkdir(parents=True, exist_ok=True)
        BASELINE_PATH.write_text(json.dumps(candidate, indent=2))
        logger.info('New baseline saved: %s', candidate)

    return result


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s %(message)s')
    result = main()
    print(json.dumps(result, indent=2))

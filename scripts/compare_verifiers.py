"""Compare TF-IDF and NLI grounding verifiers on the golden QA set.

Runs both verifiers against the same retrieved chunks for each golden
question, then prints a row-per-question table and writes a CSV.

The "answer" scored here is a deterministic synthetic answer built from
the expected_answer_contains keywords — it mirrors what a well-behaved
generator would produce, and deliberately avoids LLM output so the
comparison is not polluted by generator non-determinism. This lets the
disagreement stats reflect *verifier* behaviour, not generator variance.

Run:
    python scripts/compare_verifiers.py

Writes:
    benchmarks/verifier_comparison.csv

If the NLI model cannot load (no download, no disk), the script still
completes — NLI columns will show `nli_unavailable` and the row is
logged as a skip rather than a failure.
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

# Let the script run from repo root via `python scripts/compare_verifiers.py`.
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.services.retrieval_service import RetrievalService  # noqa: E402
from app.services.verification_service import VerificationService  # noqa: E402
from app.verification.nli_verifier import NLIVerifier  # noqa: E402

GOLDEN_QA_PATH = ROOT / 'data' / 'golden_qa' / 'golden_qa_v1.json'
OUTPUT_CSV = ROOT / 'benchmarks' / 'verifier_comparison.csv'


def build_synthetic_answer(question: str, keywords: list[str]) -> str:
    """Construct a deterministic answer that should be supported by the
    expected source. Uses the question stem and the expected keywords so
    the verifier has real content to score against the retrieved chunks.
    """
    keyword_blob = ', '.join(keywords)
    return f'{question} The answer relies on {keyword_blob}, as described in the relevant procedure document.'


def run() -> None:
    if not GOLDEN_QA_PATH.exists():
        print(f'ERROR: golden QA file not found at {GOLDEN_QA_PATH}')
        sys.exit(1)

    golden = json.loads(GOLDEN_QA_PATH.read_text(encoding='utf-8'))
    retrieval = RetrievalService()
    tfidf = VerificationService()
    nli = NLIVerifier()

    # Probe NLI availability up front so the reader sees one clear banner.
    nli.warmup()
    nli_available = nli.is_available()
    if not nli_available:
        print(f'NLI model unavailable: {nli._load_error}')
        print('Script will complete with nli_unavailable markers.')

    rows: list[dict] = []
    agreements = 0
    disagreements: list[dict] = []

    for i, item in enumerate(golden, 1):
        question = item['question']
        keywords = item.get('expected_answer_contains', [])
        role = item.get('role', 'viewer')
        sources = item.get('expected_sources', [])

        chunks = retrieval.search_sync(
            query=question,
            top_k=5,
            role=role,
            requested_sources=sources,
        )
        if not chunks:
            # Fall back to a top-5 search without the source filter so the
            # verifier at least has *something* to score against.
            chunks = retrieval.search_sync(query=question, top_k=5, role=role, requested_sources=[])

        answer = build_synthetic_answer(question, keywords)

        tfidf_result = tfidf.check_support(answer, chunks)
        tfidf_supported = tfidf_result['supported_ratio']
        tfidf_gate = tfidf_supported >= 0.50  # ALLOW / ALLOW_WITH_WARNING band

        if nli_available:
            nli_result = nli.verify_grounding(answer, chunks)
            if nli_result.get('verifier') == 'nli_unavailable':
                nli_ent = nli_neu = nli_con = None
                nli_supported = None
                nli_gate = None
            else:
                dist = nli_result.get('label_distribution', {})
                total = max(sum(dist.values()), 1)
                nli_ent = dist.get('entailment', 0) / total
                nli_neu = dist.get('neutral', 0) / total
                nli_con = dist.get('contradiction', 0) / total
                nli_supported = nli_result['supported_ratio']
                nli_gate = nli_supported >= 0.50
        else:
            nli_ent = nli_neu = nli_con = None
            nli_supported = None
            nli_gate = None

        if nli_gate is not None:
            agrees = tfidf_gate == nli_gate
            if agrees:
                agreements += 1
            else:
                disagreements.append(
                    {
                        'id': i,
                        'question': question,
                        'tfidf_supported': round(tfidf_supported, 4),
                        'nli_supported': round(nli_supported or 0.0, 4),
                        'nli_contradiction_frac': round(nli_con or 0.0, 4),
                    }
                )

        rows.append(
            {
                'id': i,
                'question': question,
                'role': role,
                'num_chunks': len(chunks),
                'tfidf_supported_ratio': round(tfidf_supported, 4),
                'tfidf_gate_pass': tfidf_gate,
                'nli_supported_ratio': (round(nli_supported, 4) if nli_supported is not None else ''),
                'nli_entailment_frac': (round(nli_ent, 4) if nli_ent is not None else ''),
                'nli_neutral_frac': (round(nli_neu, 4) if nli_neu is not None else ''),
                'nli_contradiction_frac': (round(nli_con, 4) if nli_con is not None else ''),
                'nli_gate_pass': '' if nli_gate is None else nli_gate,
                'agree': '' if nli_gate is None else (tfidf_gate == nli_gate),
            }
        )

    # --- Write CSV ---
    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0].keys()) if rows else []
    with OUTPUT_CSV.open('w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    # --- Print summary table ---
    print('\n=== VERIFIER COMPARISON ===')
    header = f'{"#":>2}  {"tfidf":>6}  {"nli_sup":>7}  {"nli_ent":>7}  {"nli_neu":>7}  {"nli_con":>7}  {"agree":>5}  question'
    print(header)
    print('-' * len(header))
    for r in rows:
        q_short = r['question'][:60] + ('...' if len(r['question']) > 60 else '')
        print(
            f'{r["id"]:>2}  '
            f'{r["tfidf_supported_ratio"]:>6}  '
            f'{r["nli_supported_ratio"]:>7}  '
            f'{r["nli_entailment_frac"]:>7}  '
            f'{r["nli_neutral_frac"]:>7}  '
            f'{r["nli_contradiction_frac"]:>7}  '
            f'{r["agree"]!s:>5}  '
            f'{q_short}'
        )

    if nli_available:
        total_scored = agreements + len(disagreements)
        agreement_rate = agreements / total_scored if total_scored else 0.0
        print('\n=== SUMMARY ===')
        print(f'Questions scored:     {total_scored}')
        print(f'Gate agreement:       {agreements} / {total_scored} ({agreement_rate:.1%})')
        print(f'Disagreements:        {len(disagreements)}')
        if disagreements:
            # Sort by absolute TF-IDF/NLI difference, surface top-3.
            def _delta(d: dict) -> float:
                return abs(d['tfidf_supported'] - d['nli_supported'])

            ranked = sorted(disagreements, key=_delta, reverse=True)
            print('\nTop-3 disagreements (by |tfidf-nli|):')
            for d in ranked[:3]:
                print(
                    f'  #{d["id"]:>2}  '
                    f'tfidf={d["tfidf_supported"]:.2f}  '
                    f'nli={d["nli_supported"]:.2f}  '
                    f'contra={d["nli_contradiction_frac"]:.2f}  '
                    f'{d["question"][:80]}'
                )
    print(f'\nCSV written to: {OUTPUT_CSV}')


if __name__ == '__main__':
    run()

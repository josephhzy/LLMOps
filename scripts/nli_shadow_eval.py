"""NLI shadow evaluation runner.

Runs the existing 18 golden QA pairs through the full RAG pipeline,
captures the TF-IDF verification verdict (the one actually returned to
the user), and scores the same (answer, chunks) tuple with the NLI
cross-encoder as a shadow path. Writes disagreements to
`evaluation/nli_shadow_results.json`.

Usage:
    py scripts/nli_shadow_eval.py

No flags. Reads `data/golden_qa/golden_qa_v1.json`, writes
`evaluation/nli_shadow_results.json`. Non-zero exit if the NLI model
cannot be loaded (no internet, missing cache, etc.) — the shadow run
can't happen without it.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Disable external LLM backends so this runs offline.
os.environ.setdefault('GENERATION_BACKEND', 'template')


async def main() -> int:
    from app.models.api import QueryRequest
    from app.services.rag_service import RAGService
    from app.verification.nli_verifier import NLIVerifier

    qa_path = ROOT / 'data' / 'golden_qa' / 'golden_qa_v1.json'
    out_path = ROOT / 'evaluation' / 'nli_shadow_results.json'
    out_path.parent.mkdir(parents=True, exist_ok=True)

    golden = json.loads(qa_path.read_text(encoding='utf-8'))
    print(f'Loaded {len(golden)} golden QA pairs')

    nli = NLIVerifier()
    if not nli.is_available():
        print(f'NLI model unavailable: {nli._load_error}', file=sys.stderr)
        return 2
    print(f'NLI model loaded: {nli.model_name}')

    rag = RAGService()

    entries: list[dict] = []
    disagreements: list[dict] = []
    tfidf_pass_nli_contradiction = 0
    tfidf_pass_nli_neutral = 0
    tfidf_reject_nli_entailment = 0

    for i, qa in enumerate(golden):
        req = QueryRequest(question=qa['question'], top_k=5, enable_citations=True)
        try:
            resp = await rag.answer(req, role=qa.get('role', 'viewer'), user_id='nli-shadow')
        except Exception as exc:
            # Injection pre-check or retrieval failure — skip from shadow set.
            entries.append(
                {
                    'idx': i,
                    'question': qa['question'],
                    'error': f'{type(exc).__name__}: {exc}',
                }
            )
            continue

        # Re-retrieve the same chunks that backed this answer — the
        # response only carries citations (snippets), not full RetrievedChunk
        # objects, so pull the chunks directly from the retriever again with
        # the same parameters used above.
        chunks = await rag.retrieval.search(qa['question'], req.top_k, qa.get('role', 'viewer'), [])
        # Reranker is part of the real path too.
        chunks = await rag.reranker.rerank(qa['question'], chunks)

        # TF-IDF verdict is the one already on the response. Re-compute
        # directly from the same answer+chunks for a clean side-by-side.
        tfidf_result = rag.verification.verify_grounding(resp.answer, chunks)
        nli_result = nli.verify_grounding(resp.answer, chunks)

        entry = {
            'idx': i,
            'question': qa['question'],
            'role': qa.get('role', 'viewer'),
            'answer': resp.answer,
            'policy_action': resp.policy_action.value
            if hasattr(resp.policy_action, 'value')
            else str(resp.policy_action),
            'tfidf': {
                'supported_ratio': tfidf_result['supported_ratio'],
                'num_claims': tfidf_result['num_claims'],
            },
            'nli': {
                'supported_ratio': nli_result['supported_ratio'],
                'num_claims': nli_result['num_claims'],
                'label_distribution': nli_result['label_distribution'],
            },
        }
        entries.append(entry)

        # Disagreement tracking — per-sentence join across the two verifiers.
        tfidf_verdicts = tfidf_result.get('sentence_verdicts') or []
        nli_verdicts = nli_result.get('sentence_verdicts') or []

        for j, (tv, nv) in enumerate(zip(tfidf_verdicts, nli_verdicts, strict=False)):
            tfidf_supported = bool(tv.get('supported'))
            nli_label = nv.get('label')
            sentence_dis = None
            if tfidf_supported and nli_label == 'contradiction':
                sentence_dis = 'tfidf_pass_nli_contradiction'
                tfidf_pass_nli_contradiction += 1
            elif tfidf_supported and nli_label == 'neutral':
                sentence_dis = 'tfidf_pass_nli_neutral'
                tfidf_pass_nli_neutral += 1
            elif (not tfidf_supported) and nli_label == 'entailment':
                sentence_dis = 'tfidf_reject_nli_entailment'
                tfidf_reject_nli_entailment += 1

            if sentence_dis:
                disagreements.append(
                    {
                        'qa_idx': i,
                        'question': qa['question'],
                        'sentence_idx': j,
                        'sentence': nv.get('sentence'),
                        'tfidf_max_similarity': tv.get('max_similarity'),
                        'tfidf_supported': tfidf_supported,
                        'nli_label': nli_label,
                        'nli_entailment_score': nv.get('entailment_score'),
                        'nli_contradiction_score': nv.get('contradiction_score'),
                        'disagreement_type': sentence_dis,
                    }
                )

        print(
            f'  [{i + 1}/{len(golden)}] tfidf={tfidf_result["supported_ratio"]:.2f} '
            f'nli={nli_result["supported_ratio"]:.2f} '
            f'labels={nli_result["label_distribution"]}'
        )

    summary = {
        'n_questions': len(golden),
        'n_evaluated': sum(1 for e in entries if 'error' not in e),
        'model': nli.model_name,
        'entailment_threshold': nli.entailment_threshold,
        'disagreements_total': len(disagreements),
        'disagreement_counts': {
            'tfidf_pass_nli_contradiction': tfidf_pass_nli_contradiction,
            'tfidf_pass_nli_neutral': tfidf_pass_nli_neutral,
            'tfidf_reject_nli_entailment': tfidf_reject_nli_entailment,
        },
    }

    out = {
        'summary': summary,
        'entries': entries,
        'disagreements': disagreements,
    }
    out_path.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding='utf-8')
    print(f'\nWrote {out_path}')
    print('Summary:', json.dumps(summary, indent=2))
    return 0


if __name__ == '__main__':
    sys.exit(asyncio.run(main()))

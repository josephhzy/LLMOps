# Golden QA dataset spec

The golden QA set is the offline benchmark used by:

- `pipelines/run_evaluation.py` — drives the promotion gate.
- `app/services/evaluation_service.py` — computes per-model metrics.
- `benchmarks/locustfile.py` — draws realistic questions for the load test.

## Where it lives

`data/golden_qa/golden_qa_v1.json` — 18 questions, JSON array. Each entry:

```json
{
  "question": "What is the notification timeline for a P1 incident?",
  "expected_answer_contains": ["15 minutes", "duty officer"],
  "expected_sources": ["sop-001"],
  "role": "viewer"
}
```

| Field | Meaning |
|-------|---------|
| `question` | Input to `POST /v1/query` |
| `expected_answer_contains` | List of substrings the answer text should include (lowercased contains-check). Drives the `keyword_coverage` component of the score, which is now aggregated and reported in the benchmark metrics. |
| `expected_sources` | Document IDs that must appear in the response citations. Drives `citation_coverage`. |
| `role` | Role the query is executed as. Lets us check ACL-filtered cases (admin-only documents should not surface for `viewer`). |

## Current coverage

18 questions across 7 source documents. Role distribution: 16 viewer, 2 admin (both against `sop-002`, which is the evidence-handling SOP marked admin-only).

| Source doc | Questions |
|------------|-----------|
| `sop-001` (incident response) | 3 |
| `sop-002` (evidence handling, admin) | 2 |
| `sop-003` (access control) | 3 |
| `sop-004` (data classification) | 3 |
| `sop-005` (change management) | 3 |
| `policy-001` (acceptable use) | 2 |
| `guide-001` (onboarding) | 2 |

Question types:
- Single-fact lookup ("what hashing algorithm", "how long is the probation period"): ~10
- Multi-fact list recall ("what are the data classification tiers", "what must a change request include"): ~5
- Procedural ("what happens after a post-incident review", "what is the emergency change procedure"): ~3

## Known weaknesses of v1

- **Size.** 18 is small. It catches gross regressions but not subtle ones. Target for v2: 60-100 questions, same sources.
- **Role coverage.** Only 2 admin-only questions. Needs more to stress the ACL filter.
- **No adversarial items.** Every question has evidence in the corpus. A production set should include ~20% out-of-corpus questions that must trigger `ABSTAIN`, so the benchmark measures refusal rate as well as answer quality.
- **No paraphrase pairs.** Every question is a single phrasing. Adding a paraphrase per question doubles the effective size and exposes verifier brittleness.
- **No contradiction pairs.** A subset where the "correct" answer requires the model to reject an incorrect premise ("P1 incidents must be reported within an hour, right?") would expose hallucination propagation.

## Scoring (how `run_evaluation.py` uses it)

For each question, the evaluator computes:

- `keyword_coverage` — `1.0` if all `expected_answer_contains` strings are present in the answer (case-insensitive), else the fraction that are present. This per-question value is now aggregated and reported as the mean `keyword_coverage` in the benchmark metrics.
- `citation_coverage` — fraction of `expected_sources` that appear in the returned citations.
- `grounded_support` — the verifier's `supported_ratio` for this answer (the fraction of answer claims grounded in retrieved evidence). The aggregate `grounded_support` metric is the mean of this per-question ratio; it now reflects the true verifier `supported_ratio` rather than the retrieval/grounding blend.
- The retrieval+grounding blend (`0.4 * retrieval score + 0.6 * supported_ratio`) is reported separately per question as `confidence`, so it is no longer conflated with `grounded_support`.
- `refusal_correctness` — *(planned, not yet implemented)* — would score `1.0` when the policy action matches expectation, but the golden QA set does not yet label which questions should refuse.

Aggregate metrics reported:

- Mean `grounded_support` across all questions — promotion gate threshold 0.75.
- Mean `citation_coverage` across all questions — promotion gate threshold 0.70.
- Per-question failures listed for debugging.

## Curation process for v2 (proposed)

1. Pick a topic area (e.g., new SOP). Read the source doc end-to-end.
2. Draft 6-10 questions: 3-4 single-fact, 2-3 multi-fact, 1-2 procedural.
3. For each, write the `expected_answer_contains` list by picking 2-4 substrings that a *correct* answer would almost certainly include. Avoid words that also appear in other documents to avoid false passes.
4. Add 1-2 paraphrase versions of each question.
5. Add 1-2 adversarial "not in corpus" questions to force `ABSTAIN`.
6. Peer-review the set before committing — the biggest risk is subtly wrong expected substrings that make a correct answer score zero.

## Versioning

The file is suffixed `_v1`. A new version is a new file (`golden_qa_v2.json`), never an edit-in-place, because the promotion history records which QA version a model was scored against.

When v2 ships, the evaluator runs whichever version is named in `pipelines/run_evaluation.py` (currently `golden_qa_v1`); older baselines stay comparable by re-running them against the old file. This is why `model_registry/PROMOTION_DEMO.md` records which QA version each gate decision was based on.

# Verification upgrade plan: TF-IDF overlap → cross-encoder NLI

## Status (2026-04-16)

Implemented in `app/verification/nli_verifier.py` (primary model `cross-encoder/nli-deberta-v3-base`, ~180MB; graceful fallback to `cross-encoder/nli-MiniLM2-L6-H768` if the primary fails to load). Shadow-mode comparison script at `scripts/compare_verifiers.py`. Current disagreement rate on 18 golden QA pairs: **22.2%** (4 / 18 at the `>=0.50` supported-ratio gate). Raw run: `benchmarks/verifier_comparison.csv`. TF-IDF remains the default policy gate; the disagreement sample is too small to justify cutting over yet, and the cross-encoder forward-pass cost is still the dominant latency argument on CPU.

**Note on disagreement interpretation:** The sentence-level disagreement log (42 of 43 cases are `tfidf_pass_nli_neutral`) reveals a precondition problem: the generated answers in the golden set contain raw document fragments with inline citation brackets (e.g. `Scope] # SOP-001: ... [1]`), not clean prose claims. The NLI model returns near-zero entailment scores on these inputs because they are not parseable claim-evidence pairs. The 22.2% gate-level disagreement rate should therefore not be treated as a measure of NLI accuracy or conservatism — it reflects an upstream answer-quality issue. Before the gate-flip decision can be made, either (a) the answer formatter must be fixed to emit clean sentences before the verifier receives them, or (b) a re-run against properly formatted answers must be conducted and compared.

`NLIVerifier.verify_grounding` dispatches on argument type: passed `(claim: str, evidence: str)` it returns the primitive `{entailment, neutral, contradiction, verified}` shape; passed `(answer: str, chunks: list[RetrievedChunk])` it returns the richer per-claim/per-chunk shape the RAG orchestrator expects. The primitive is also exposed directly as `verify_pair(claim, evidence)` and raises `NotImplementedError` when the model cannot load rather than fabricating neutral verdicts.

## Current state

`app/services/verification_service.py` implements `VerificationService.check_support`. For each sentence in a generated answer, it computes the max TF-IDF cosine similarity against every retrieved evidence chunk. A sentence counts as "supported" when that similarity is at least `settings.grounding_threshold` (default `0.3`). The final `supported_ratio` is the fraction of sentences that clear the threshold.

This is lexical-overlap scoring. It is fast, deterministic, and cheap. It is also not entailment.

## Known failure modes

### False reject on paraphrase
The answer says "P1 incidents require duty officer notification within fifteen minutes." The chunk says "Priority 1 events must trigger contact to the on-call officer no later than a quarter of an hour." Semantically identical. Lexically, `P1` and `Priority 1` differ, `fifteen minutes` and `a quarter of an hour` do not overlap in tokens, and TF-IDF scores the pair low. A correct answer is flagged as unsupported.

### False accept on fabricated citation
The chunk discusses data classification tiers: `public`, `internal`, `confidential`, `restricted`. The answer fabricates "The `restricted` tier permits unauthenticated read access." TF-IDF sees heavy token overlap — `restricted`, `access`, `tier` — and scores the sentence as supported. An entailment-aware system would catch the contradiction (the real chunk almost certainly says the opposite), a lexical system cannot.

### Numerical claim errors
"Hashes must use SHA-256." vs. "Hashes should use SHA-512." Token overlap is near-complete; a sentence-level semantic model would still treat these as aligned (both assert a hashing requirement), but a token-level lexical model treats them as aligned, and an *NLI* model treats them as contradictory. Our TF-IDF cannot distinguish.

### Citation smuggling
If the model emits a claim followed by `[2]`, and chunk 2 happens to share keywords with the claim but does not actually support it, TF-IDF will usually pass the claim. NLI would score `neutral` or `contradiction` on that (claim, chunk-2) pair and surface it.

## Upgrade target

Cross-encoder NLI model scoring the probability of `entailment`, `neutral`, and `contradiction` for each (claim, chunk) pair.

Candidate models:

| Model | Size | Strengths | Notes |
|-------|------|-----------|-------|
| `cross-encoder/nli-deberta-v3-base` | ~180MB | Strong on MNLI/SNLI, widely benchmarked, permissive licence | Default recommendation |
| `MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli` | ~180MB | Trained on FEVER + ANLI, better on adversarial samples | Good second choice |
| `cross-encoder/nli-MiniLM2-L6-H768` | ~80MB | Much smaller, faster on CPU | Use if latency budget is tight |

On CPU, expected per-pair latency is 200-500ms for DeBERTa-v3-base. With `top_k = 5` chunks and ~3 claims per answer, that is 15 forward passes per query, or ~3-7s of verification overhead. Acceptable for async background scoring, painful for synchronous p95. The upgrade should gate on latency measurements; if CPU is too slow, either (a) batch the forward passes, (b) run verification as a shadow path (log but do not block) during rollout, or (c) require GPU.

## Interface

Implemented in `app/verification/nli_verifier.py`. The class shape:

```python
class NLIVerifier:
    def __init__(self, model_name: str, entailment_threshold: float = 0.70, device: str = "cpu"): ...
    def warmup(self) -> None: ...
    def verify_grounding(self, answer: str, chunks: list[RetrievedChunk]) -> dict: ...
```

`verify_grounding` returns:

```python
{
    "supported_ratio": float,          # fraction of claims with best-chunk entailment >= threshold
    "num_claims": int,
    "sentence_verdicts": [
        {
            "sentence": str,
            "label": "entailment" | "neutral" | "contradiction",
            "entailment_score": float,       # P(entailment) from the best chunk
            "best_chunk_idx": int,
        },
        ...
    ],
    "label_distribution": {
        "entailment": int,
        "neutral": int,
        "contradiction": int,
    },
    "verifier": "nli",
    "model": str,
}
```

This is a strict superset of what the TF-IDF verifier returns, so existing consumers keep working. The `label_distribution` field reports per-label counts (entailment, neutral, contradiction) rather than a scalar overlap number.

## Evaluation plan

### Held-out set construction
Build a small held-out set where the ground truth is known:

1. **True positives** (answer actually supported) — take golden QA expected answers and run them against their expected sources. The correct citation should score high.
2. **Paraphrase positives** — rewrite N golden answers using synonyms and rephrasing without changing meaning. Correct answer, different words. TF-IDF is expected to false-reject here; NLI is expected to pass.
3. **Lexically-similar negatives** — craft N sentences that share keywords with the evidence but contradict it (e.g., invert a boolean, change a numeric value). TF-IDF is expected to false-accept; NLI is expected to flag.
4. **Partial-support cases** — answers where one clause is supported and another is invented. Check whether both verifiers can report per-claim verdicts, not just a scalar.

Target size: 50-100 pairs, roughly balanced across the four categories.

### Metrics to report

| Metric | TF-IDF (baseline) | NLI |
|--------|-------------------|-----|
| Precision (claim labelled supported is actually supported) | TBD | TBD |
| Recall (actually-supported claim is labelled supported) | TBD | TBD |
| False-accept rate on lexically-similar negatives | expected high | expected low |
| False-reject rate on paraphrase positives | expected high | expected low |
| Mean latency per query (ms) | TBD | TBD |
| p95 latency per query (ms) | TBD | TBD |

Publish results in `benchmarks/VERIFICATION_RESULTS.md` once the run is done.

## Rollout

1. **Shadow mode** — run NLI in parallel with TF-IDF, log both scores, use TF-IDF for the policy decision. Collect disagreement distribution for a week.
2. **Gate flip** — switch the policy post-check to NLI once shadow-mode agreement and latency are acceptable.
3. **Decommission TF-IDF verifier** — keep the class, keep the tests, move it to `app.verification.tfidf_verifier` as an explicit fallback for when NLI isn't loaded.

## Swap location

`NLIVerifier.verify_grounding` is implemented, so the wiring is one line. In `app/api/dependencies.py` (or wherever the `RAGService` is constructed), replace:

```python
verification = VerificationService()
```

with:

```python
from app.verification.nli_verifier import NLIVerifier
verification = NLIVerifier(model_name=settings.nli_model_name)
verification.warmup()
```

The matching `nli_model_name` field is already present in `app/core/config.py`, so no config change is needed.

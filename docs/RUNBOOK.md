# Runbook: responding to incidents

These procedures require no prior codebase knowledge. Each step that references a file path includes the path inline — no additional reading required.

The five scenarios covered are the ones this platform is designed to handle. For anything else (pod won't schedule, node OOM, etc.), fall back to generic Kubernetes troubleshooting.

---

## 1. Corpus poisoning suspected

### Signals
- Sudden change in answer content for queries that were previously stable.
- A customer / reviewer reports an answer that recommends or describes something contradicting policy.
- `ABSTAIN` rate drops to near-zero on queries that previously abstained.

### Stop the bleeding (≤ 5 minutes)
1. **Identify the suspicious document.** The audit trail records `corpus/ingest` events with document IDs:
   ```
   grep '"event_type": "corpus"' data/audit.jsonl | tail -20
   ```
   Look for recent document additions or updates that coincide with the signal.

2. **Revoke the document.** Removes it from retrieval immediately (revocation is evaluated at query time, not only at re-ingest):
   ```
   curl -X POST http://localhost:8000/v1/admin/corpus/revoke \
     -H "X-API-Key: $ADMIN_KEY" \
     -H "Content-Type: application/json" \
     -d '{"doc_id": "<SUSPECT_ID>", "reason": "Suspected poisoning — investigation"}'
   ```

3. **Rebuild the index** to flush any cached state:
   ```
   curl -X POST http://localhost:8000/v1/ingest/rebuild-index-sync \
     -H "X-API-Key: $ADMIN_KEY"
   ```

### Investigate (≤ 60 minutes)
1. Pull the document source (`data/sample_docs/<doc_id>.md` or the upstream feed) and diff against the previous known-good version.
2. Replay a handful of queries that returned the suspicious answer. `scripts/replay_audit.py --query-id <trace_id>` reconstructs the exact retrieved chunks and verification result from the audit log.
3. If the document really was poisoned: file a post-mortem, widen the revocation to any related documents, and add a fingerprint check to the ingestion pipeline so the same content cannot be re-ingested.
4. If the document is fine and the drift came from elsewhere: proceed to section 4 (drift flag).

### Recovery
- Leave the document revoked until root cause is confirmed. Un-revocation is a deliberate act, not a default.

---

## 2. Injection spike

### Signals
- `InjectionSpike` alert firing (`policy_action_total{action="BLOCK"}` rate exceeding threshold).
- Local (Docker Compose): `docker compose logs api | grep policy_violation` shows a burst of the same or similar patterns from one client.
- Kubernetes: `kubectl logs -l app=llm-ops-api -n llm-ops | grep policy_violation`

### Stop the bleeding (≤ 5 minutes)
1. **Inspect the block events.** Every block writes to audit:
   ```
   grep '"action": "block_injection"' data/audit.jsonl | tail -50 | jq .
   ```
2. **Identify the source.** API-key or IP (once logged — today we log the question preview, not the caller identity, which is a known gap). If a single caller is responsible, revoke their API key at the auth layer. (In this demo, there are only two shared keys; per-user revocation would require the JWT/OAuth upgrade noted in docs/09_threat_model.md.)
3. **If the block rate is from legitimate users (false positives):**
   - Do NOT disable the pre-check. Instead, tighten the specific pattern causing false positives — see `app/services/policy_service.py::INJECTION_PATTERNS`.
   - Redeploy with the tightened pattern.

### Investigate
1. Export the blocked questions (the audit records a 100-char preview): `jq 'select(.action=="block_injection") | .details' data/audit.jsonl`. The preview is not full text by design — to get full text, check the FastAPI access log if enabled.
2. If the attacks are sophisticated (paraphrased, encoded, indirect): the regex set is inadequate. Move to the semantic / classifier upgrade path in `docs/INJECTION_EVAL.md`.
3. Update `docs/INJECTION_EVAL.md` "known gaps" section with the new attack shape.

### Recovery
- Do not tune thresholds under pressure. Any change to the pre-check pattern set must go through the promotion gate or an explicit runbook entry with rollback plan.

---

## 3. Latency regression

### Signals
- `QueryP95High` alert firing.
- Customer reports of slow queries.
- Grafana shows p95 of `/v1/query` rising over hours/days.

### Triage (≤ 10 minutes)
1. Pull per-stage latency from metrics:
   - `llm_ops_generation_duration_seconds` — LLM backend or template
   - `llm_ops_retrieval_duration_seconds`
   - Verification is not yet instrumented — there is no verification latency metric, so its cost has to be inferred from the gap between total request latency (`llm_ops_request_duration_seconds`) and the two stages above.

   One of these will dominate the regression.

2. **If `llm_ops_generation_duration_seconds` dominates:**
   - Check the LLM backend's own dashboard (Ollama / OpenAI-compat endpoint).
   - If the backend is overloaded: scale the backend OR temporarily switch `GENERATION_BACKEND=template` to shed the hot path. Template is lossy but stable.

3. **If `llm_ops_retrieval_duration_seconds` dominates:**
   - Check ChromaDB persistent data size (`du -sh chroma_data/`). If the corpus has grown unexpectedly: the ingestion pipeline may have duplicated documents.
   - Rebuild the index from scratch: `rm -rf chroma_data && make ingest`. Only do this after a snapshot of the current state.

4. **If verification dominates (inferred — the residual after generation and retrieval, since this stage has no metric yet):**
   - You've probably swapped in the NLI verifier (`app/verification/nli_verifier.py`) and it's running on CPU. Either batch verification (`supported_ratio` in shadow mode) or move NLI to a dedicated worker.

5. **If NOTHING dominates but p95 is high:**
   - Check `uvicorn` worker count. Demo default is 1 — production should be `2 * cpu_count`.
   - Check for a pod CPU-throttling event on the orchestrator.

### Recovery
- Once the source is identified, page ownership of the dependency and roll back the triggering change if it's a recent release.

---

## 4. Model drift flagged

### Signals
- Weekly evaluation job reports `grounded_support` or `citation_coverage` dropping across the golden QA set.
- `AbstainRateHigh` alert firing in production.
- A recently-promoted model is in production (`GET /v1/admin/registry/active`).

### Triage (≤ 15 minutes)
1. Confirm the regression is not a golden-QA change. `diff` the current `data/golden_qa/golden_qa_v1.json` against the version last-known-good.
2. Pull the evaluation result for the current production model: `curl /v1/admin/registry/active` returns the `eval_snapshot` recorded at promotion.
3. Rerun the evaluation locally: `make evaluate`. Compare against the snapshot.

### Rollback decision
- If current-production `grounded_support` is below 0.70 (5% margin below the gate), roll back to the previous production model.
- If between 0.70 and 0.75, flag but don't rollback — investigate whether the regression is a golden-QA artefact.

### Rollback procedure
1. Identify the previous production model from the registry:
   ```
   curl /v1/admin/registry | jq '[.[] | select(.status=="candidate" and (.notes // "" | contains("Demoted")))]'
   ```
   The most recently demoted candidate is the previous production model.

2. Promote it back:
   ```
   curl -X POST /v1/admin/registry/promote \
     -H "X-API-Key: $ADMIN_KEY" \
     -H "Content-Type: application/json" \
     -d '{"model_id": "<PREV_ID>", "new_status": "production", "eval_metrics": {"grounded_support": <LAST_GOOD>, "citation_coverage": <LAST_GOOD>}}'
   ```
   The demotion/promotion dance is atomic in `ModelRegistry.promote` — if the new promotion fails, the previous demotion is rolled back.

### Investigate
- Was the promoted model gated on a golden-QA version that has since shifted? If so, fix the golden-QA pinning in `ModelRegistryEntry.eval_snapshot` to record the QA version alongside the metrics.
- Was there a prompt template change between the promoted model and the previous one? `prompt_version` is versioned on purpose; diff them.

---

## 5. Revocation not propagating

### Signals
- A document was revoked via `/v1/admin/corpus/revoke` but queries still surface it in citations.
- Customer reports seeing content from a document they believe was retired.

### Confirm
1. Confirm the revocation was written:
   ```
   grep '"action": "revoke"' data/audit.jsonl | grep <doc_id>
   ```
   Expected: an `outcome: success` event.

2. Confirm the corpus state:
   ```
   curl /v1/admin/corpus/documents | jq '.documents[] | select(.doc_id == "<doc_id>")'
   ```
   Expected: `status: revoked`.

3. If the audit event is missing: the revocation request did not reach the handler. Check access logs.

### Fix the propagation path
- Retrieval applies the ACL / revocation filter at query time by reading chunk metadata with `status: revoked`. If chunks are still surfacing, one of:

1. **The chunk metadata was not updated.** The revocation updates document status but requires `update_metadata` on all chunk IDs owned by that document. Verify:
   ```
   # From Python, inside the project:
   py -c "from app.services.corpus_service import CorpusService; print(CorpusService().get_document('<doc_id>'))"
   ```
   If the document shows `revoked` but chunks are still returned in queries: force a re-index (`/v1/ingest/rebuild-index-sync`).

2. **Stale cache.** If the retrieval service caches filter results, invalidate the cache. (Today there is no such cache in the default path — but any custom reranker in front of retrieval is a candidate.)

3. **Race condition with in-flight queries.** Requests started before the revocation completes may still return the document. This is expected behaviour; subsequent requests will not.

### Prevent recurrence
- If the same document revocation loop broke twice: add an integration test that revokes a document, then queries for it, and asserts `sources=[]` or `status=revoked` in the citations.

---

## Non-incident operations

### Daily (5 minutes)
- `curl /health/ready` — sanity check.
- `curl -H "X-API-Key: ${ADMIN_KEY:-dev-admin-key}" /metrics | grep policy_action` — did the block rate look normal overnight?
- Glance at the audit log tail: `tail -20 data/audit.jsonl | jq .` — anything unusual?

### Weekly
- Run `make evaluate`. Compare against baseline.
- Review `data/audit.jsonl` size; archive and rotate if >100MB.

### After any model promotion
- Run the smoke query (any question from golden QA) against the new production model. Compare answer against the previous one on the same question.
- Tail the audit log for 30 seconds to confirm no unexpected BLOCK or ABSTAIN bursts.

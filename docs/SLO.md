# Service Level Objectives (proposed)

These are the SLO numbers the platform is **designed to support**. They are not production-measured commitments. A 10-user / 30s locust smoke run against the `template` backend on a single node has been captured in the README under "Load numbers (measured)" — `POST /v1/query` p95 was 100ms there, comfortably inside the 1500ms target; concurrency-50 has since been measured (p95 ~2400ms), which EXCEEDS the 1500ms target — that is the single-worker ceiling, since the demo default is one uvicorn worker. Only the concurrency-100 run and the soak test remain. Methodology lives in `benchmarks/LOAD_TEST.md`. Treat the table below as the contract, not as the observed values.

## Availability

| Level | Target | Measurement | Error budget (28 days) |
|-------|--------|-------------|-------------------------|
| Overall API availability | 99.5% | `1 - (5xx + timeouts) / total_requests` at the ingress | 3h 22min |
| `POST /v1/query` availability | 99.5% | as above, filtered to `/v1/query` | 3h 22min |
| `/health/*` availability | 99.9% | Kubernetes liveness/readiness probe success | 40min |

Error budget policy: when 50% of the monthly budget is burned before day 14, the on-call engineer pauses non-rollback releases.

## Latency

Targets assume `generation_backend=template` (no LLM). With Ollama or an OpenAI-compatible backend, latency is dominated by the LLM and the targets below do not apply.

| Endpoint | p50 target | p95 target | p99 target |
|----------|-----------|-----------|-----------|
| `POST /v1/query` (template) | ≤ 400ms | ≤ 1500ms ¹ | ≤ 2500ms |
| `POST /v1/query` (Ollama / OpenAI-compat) | document per model | document per model | document per model |
| `GET /health/ready` | ≤ 50ms | ≤ 150ms | ≤ 300ms |
| `GET /v1/admin/corpus/status` | ≤ 100ms | ≤ 300ms | ≤ 500ms |

¹ p95 ≤ 1500ms and p50 ≤ 400ms are both met at c10 (p50=40ms, p95=100ms); single-worker c50 load-tested at p50=1000ms, p95=2400ms — both targets exceeded. Multi-worker deployment (e.g., `--workers 4`) or horizontal scaling required.

Measurement window: 28-day rolling. Reported at the ingress; in-process histograms (`app/core/metrics.py`) are the source of truth for per-stage latency breakdowns.

## Quality

| Metric | Target | Source |
|--------|--------|--------|
| `grounded_support` on golden QA | ≥ 0.75 | `pipelines/run_evaluation.py` — **also the production promotion gate** |
| `citation_coverage` on golden QA | ≥ 0.70 | as above |
| Injection-block precision (benign rate blocked) | ≤ 0.5% | `docs/INJECTION_EVAL.md` once run |
| Injection-block recall (attacks blocked) | ≥ 0.85 on PromptBench subset | `docs/INJECTION_EVAL.md` once run — current baseline 0/15 (classifier not yet built) |
| Verification `ABSTAIN` rate (on-corpus queries) | ≤ 5% | `POLICY_ACTION` metric label `ABSTAIN` / total |

The quality SLOs differ from latency/availability SLOs in that they are measured on an offline benchmark run per release, not continuously. A release that regresses them is the bigger trigger than a single bad query at runtime.

## Governance

| Metric | Target |
|--------|--------|
| Revocation propagation (`/revoke` to retrieval exclusion) | ≤ 60 seconds after index rebuild completes |
| Audit-log write success | 100% (failures are a hard block on the request) |
| Promotion gate decision latency | ≤ 5 seconds |

## Alerting rules (Prometheus AlertManager, proposed)

The rules that translate the SLOs above into pages live in [`infra/k8s/alerts.yaml`](../infra/k8s/alerts.yaml). That file is the source of truth — when a real Prometheus instance is fronting the service, load it via a `PrometheusRule` CRD or equivalent static config.

Summary of what is alerted on (see the YAML for the full expressions):

| Group | Alert | Fires when | Severity |
|-------|-------|-----------|----------|
| `llm_ops_availability` | `QueryErrorRateHigh` | `/v1/query` 5xx rate > 0.5% for 5m | page |
| `llm_ops_latency` | `QueryP95High` | `/v1/query` p95 > 1.5s for 10m | page |
| `llm_ops_quality` | `AbstainRateHigh` | `ABSTAIN` share > 15% for 15m | warn |
| `llm_ops_quality` | `InjectionSpike` | `BLOCK` rate > 0.5/s for 5m | warn |
| `llm_ops_governance` | `AuditLogWriteFailing` | any audit-write failure in 5m | page |

## What these SLOs deliberately do NOT cover

- **LLM provider SLAs.** When `GENERATION_BACKEND` is `ollama` or `openai_compat`, the upstream model provider's availability and latency are a dependency, not a commitment we can honour ourselves.
- **Corpus freshness.** A separate concern — if the corpus hasn't been re-ingested for N days, answers may be stale even though the API is 100% available.
- **Cold-start latency.** The first request after a deploy pays the model-load cost. This is scoped to the deploy-rollout SLO, not steady-state latency.

## Review cadence

- Monthly review of error-budget burn and p95 trend.
- After any `grounded_support` or `citation_coverage` regression in the evaluation pipeline: decide to roll back the new model or accept the new baseline.
- Quarterly review of the SLO targets themselves — tighten anything we are comfortably beating, loosen anything that is chronically burning budget.

# Load test methodology

This document describes how to run the load test for the LLM Ops RAG API and how to report results. The baseline c10 and c50 runs **are committed** (`benchmarks/results/run-c10_stats.csv`, `run-c50_stats.csv`, summarised in the README "Load numbers (measured)" section); only the c100 saturation run and the 10-minute soak are still pending. The methodology and the locustfile are committed too, so the results are reproducible by anyone.

## What has run and what is pending

Publishing fabricated latency numbers is worse than publishing none. Every run is executed in a reasonably representative environment (at minimum: steady CPU frequency, warm ChromaDB, the real corpus size, real LLM or a clearly-labelled template backend) before its numbers are committed. The c10 baseline and the c50 burst run are done; the c100 saturation level and the 10-minute soak are not yet run.

## System under test

| Component | Value |
|-----------|-------|
| API | FastAPI + uvicorn, 1 worker (demo default) |
| Vector DB | ChromaDB embedded |
| Corpus size | 7 sample documents, 81 chunks after ingestion |
| Embedding model | `all-MiniLM-L6-v2` (cached after first warmup) |
| Generation backend | `template` for the headline number; `ollama` / `openai_compat` as separate runs |
| Reranker | TF-IDF (default) |
| Auth | Static `X-API-Key` header |

When results are eventually published, every one of these values must be stated next to the numbers. A latency headline without its corpus size and backend is noise.

## Test matrix

Four concurrency levels, each sustained for a warmup window then a measurement window:

| Concurrency | Warmup | Measurement | Expected behaviour |
|-------------|--------|-------------|---------------------|
| 1 | 30s | 120s | Baseline single-user latency |
| 10 | 60s | 300s | Typical interactive load |
| 50 | 60s | 300s | Burst load |
| 100 | 60s | 300s | Saturation / queue depth visible |

For each level, separate runs for:

- **`POST /v1/query`** — the headline endpoint.
- **`GET /health/ready`** — baseline; should be flat across concurrency.
- **`GET /v1/admin/corpus/status`** — mixed with `/v1/query` in an 80/20 ratio to simulate dashboards.

For `POST /v1/query`, draw questions uniformly from the 18-question golden QA set (so the cache characteristic is realistic — a small amount of repetition).

## Metrics to report

Per concurrency level, per endpoint:

- **Latency** — p50, p95, p99, max (ms). Report median across at least 3 runs.
- **Throughput** — successful requests / second, averaged over the measurement window.
- **Error rate** — 5xx and timeouts as a percentage of all requests.
- **Policy breakdown** — counts of `ALLOW`, `ALLOW_WITH_WARNING`, `ABSTAIN`, `BLOCK`. This surfaces whether the system is rejecting grounded queries under load (a common failure mode if retrieval degrades).
- **CPU and RSS** — at minimum, process-level CPU % and RSS in MB over the run.

Recommended output format for each run:

```
Concurrency: 50
Endpoint:    POST /v1/query
Backend:     template
Duration:    5m measurement after 1m warmup
Requests:    9847 (3 errors, 0.03% error rate)
RPS:         32.8
Latency:     p50=412ms  p95=1180ms  p99=2340ms  max=3812ms
Policy:      ALLOW=9210 (93.5%)  WARN=402 (4.1%)  ABSTAIN=235 (2.4%)  BLOCK=0
```

## Running the test

```bash
# Start the API in its own shell
make ingest
make dev

# In another shell, install locust if needed
pip install locust

# Run headless against the locustfile below
locust -f benchmarks/locustfile.py \
       --host http://localhost:8000 \
       --users 50 --spawn-rate 10 \
       --run-time 6m \
       --headless --csv benchmarks/results/run-c50
```

The raw CSVs land in `benchmarks/results/` (`run-c50_stats.csv` and the `_failures.csv`); the committed c10/c50 numbers are summarised in the README "Load numbers (measured)" section. Read those for the measured results.

## Environment caveats to disclose in the report

- Host CPU/RAM and whether any other heavy process is running.
- Whether `uvicorn` is running with `--reload` (it must NOT be; reload adds a file-watcher that skews latency).
- Worker count (`uvicorn --workers N`) — the demo default is 1; a real deployment would use `N = 2 * cpu_count()`.
- Whether the first-run model download has completed (it should — otherwise the first minute includes an ~90MB download that dominates).
- For Ollama runs: the `llama3.2` model size and whether GPU is in use.

## What this load test does not prove

- Multi-node behaviour. This is a single-process test.
- Durability under a pod restart mid-job. Tested separately.
- Behaviour with a corpus of realistic size (thousands of documents). The 7-document sample is a floor, not a production scale.
- Cold-start latency on fresh ChromaDB. Warmup is explicitly included in the methodology, so the headline number is hot-cache.

A credible answer to "what's your p95 at concurrency 50" must state all of the above alongside the number.

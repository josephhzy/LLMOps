# 03 — File-by-File Guide

## Repository structure
```text
llm_ops/
├── README.md
├── pyproject.toml
├── Makefile
├── LICENSE
├── .env.example
├── .gitignore
├── docker-compose.yml
├── streamlit_app.py
├── .github/
│   └── workflows/
│       └── ci.yml
├── app/
│   ├── __init__.py
│   ├── api/
│   │   ├── __init__.py
│   │   ├── main.py
│   │   ├── middleware.py
│   │   ├── dependencies.py
│   │   └── routes/
│   │       ├── __init__.py
│   │       ├── health.py
│   │       ├── query.py
│   │       ├── ingest.py
│   │       ├── jobs.py
│   │       ├── corpus.py
│   │       ├── registry.py
│   │       ├── admin.py
│   │       └── metrics.py
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py
│   │   ├── logging.py
│   │   ├── metrics.py
│   │   ├── exceptions.py
│   │   ├── security.py
│   │   ├── auth.py
│   │   └── audit.py
│   ├── domain/
│   │   ├── __init__.py
│   │   ├── ports.py
│   │   └── models.py
│   ├── models/
│   │   ├── __init__.py
│   │   ├── api.py
│   │   ├── domain.py
│   │   ├── enums.py
│   │   └── jobs.py
│   ├── services/
│   │   ├── __init__.py
│   │   ├── rag_service.py
│   │   ├── retrieval_service.py
│   │   ├── embedding_service.py
│   │   ├── vector_store.py
│   │   ├── reranker_service.py
│   │   ├── prompt_service.py
│   │   ├── model_router.py
│   │   ├── generation_service.py
│   │   ├── citation_service.py
│   │   ├── policy_service.py
│   │   ├── verification_service.py
│   │   ├── evaluation_service.py
│   │   ├── job_service.py
│   │   ├── corpus_service.py
│   │   └── model_registry.py
│   └── verification/
│       ├── __init__.py
│       └── nli_verifier.py
├── pipelines/
│   ├── __init__.py
│   ├── ingest_pipeline.py
│   ├── run_evaluation.py
│   └── run_finetune.py
├── scripts/
│   ├── _build_injection_eval_set.py
│   ├── compare_verifiers.py
│   ├── eval_injection.py
│   ├── injection_eval.py
│   ├── nli_shadow_eval.py
│   ├── promotion_gate_demo.py
│   └── replay_audit.py
├── benchmarks/
│   ├── LOAD_TEST.md
│   ├── locustfile.py
│   ├── injection_test_set.json
│   ├── injection_eval_results.json
│   ├── verifier_comparison.csv
│   └── results/
│       ├── run-c10_stats.csv
│       ├── run-c10_stats_history.csv
│       ├── run-c10_failures.csv
│       ├── run-c10_exceptions.csv
│       ├── run-c50_stats.csv
│       ├── run-c50_stats_history.csv
│       ├── run-c50_failures.csv
│       └── run-c50_exceptions.csv
├── evaluation/
│   ├── GOLDEN_QA_SPEC.md
│   ├── injection_eval_set.json
│   └── nli_shadow_results.json
├── model_registry/
│   └── PROMOTION_DEMO.md
├── ml/
│   └── prompts/
│       └── grounded_answer.yaml
├── data/
│   ├── audit.jsonl
│   ├── sample_docs/
│   │   ├── guide_001_onboarding.md
│   │   ├── policy_001_acceptable_use.md
│   │   ├── sop_001_incident_response.md
│   │   ├── sop_002_evidence_handling.md
│   │   ├── sop_003_access_control.md
│   │   ├── sop_004_data_classification.md
│   │   └── sop_005_change_management.md
│   ├── golden_qa/
│   │   └── golden_qa_v1.json
│   └── finetune/
│       ├── sample_recipe.yaml
│       └── sample_dataset.json
├── infra/
│   ├── docker/
│   │   ├── api.Dockerfile
│   │   └── worker.Dockerfile
│   └── k8s/
│       ├── namespace.yaml
│       ├── api-deployment.yaml
│       ├── service.yaml
│       ├── configmap.yaml
│       ├── ingress.yaml
│       ├── pvc.yaml
│       ├── chroma-pvc.yaml
│       ├── rbac.yaml
│       └── alerts.yaml
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── test_health.py
│   ├── test_query_api.py
│   ├── test_corpus_service.py
│   ├── test_evaluation_service.py
│   ├── test_failure_modes.py
│   ├── test_generation_service.py
│   ├── test_ingest_pipeline.py
│   ├── test_job_service.py
│   ├── test_model_registry.py
│   ├── test_policy_service.py
│   ├── test_reranker_service.py
│   ├── test_retrieval_service.py
│   ├── test_verification_service.py
│   ├── test_nli_verifier.py
│   └── test_full_query_pipeline.py
└── docs/
    ├── 01_solution_overview.md
    ├── 02_target_architecture.md
    ├── 03_file_by_file_guide.md
    ├── 04_function_reference.md
    ├── 05_deployment_and_mlop.md
    ├── 06_security_and_guardrails.md
    ├── 07_operations_runbook.md
    └── 09_threat_model.md
```

---

## Top-level files

**README.md** — Project overview, quick start, architecture diagram, API endpoint table, and project structure.

**pyproject.toml** — Python project metadata, dependency declarations, and tool configuration (ruff, pytest, mypy). Single source of truth for the build.

**Makefile** — Developer workflow shortcuts: `make install`, `make dev`, `make test`, `make lint`, `make docker-build`, etc. Ensures consistent commands across the team.

**LICENSE** — MIT license file.

**.env.example** — Template for environment variables (generation backend, LLM URL, ChromaDB settings). Copied to `.env` for local configuration.

**.gitignore** — Standard Python ignores plus project-specific exclusions (chroma_data, audit logs, coverage artifacts).

**docker-compose.yml** — Single-service Compose file for the API container with health checks, volume mounts for ChromaDB persistence, and sample data.

---

## `.github/workflows/`

**ci.yml** — GitHub Actions CI pipeline with three parallel jobs: lint (ruff check + format check), test (pytest with coverage upload to Codecov), and docker (compose build sanity check). Runs on push to main and on PRs.

---

## `app/api/`

**main.py** — FastAPI application factory with lifespan management. Registers all route modules, attaches middleware, and wires up structured logging on startup.

**middleware.py** — Error handling and metrics middleware. Catches `PolicyViolationError` and `VerificationError` into structured JSON responses, records request counts and latency to Prometheus counters/histograms.

**dependencies.py** — Dependency injection factories for FastAPI routes. Uses `lru_cache` to create singleton instances of RAGService, JobService, CorpusService, and ModelRegistry, keeping route handlers thin.

### `app/api/routes/`

**health.py** — Liveness (`/health/live`) and readiness (`/health/ready`) probes. Readiness checks dependency availability (vector store, embedding model).

**query.py** — `POST /v1/query` endpoint. Accepts a question, delegates to RAGService, returns the grounded answer with citations and policy action.

**ingest.py** — Index rebuild endpoints. Provides both async (`/v1/ingest/rebuild-index`) and synchronous (`/v1/ingest/rebuild-index-sync`) re-indexing for the corpus.

**jobs.py** — Async job management routes. Submit jobs (`/v1/jobs/submit`), poll status (`/v1/jobs/{id}`), list all jobs (`/v1/jobs`). Supports ingest, evaluate, reindex, and finetune job types.

**corpus.py** — Corpus governance API. View corpus status (`GET /v1/admin/corpus/status`), list documents (`GET /v1/admin/corpus/documents`), get a single document (`GET /v1/admin/corpus/documents/{doc_id}`), and revoke documents (`POST /v1/admin/corpus/revoke`). Admin-only operations with audit logging.

**registry.py** — Model registry API. List registry history (`/v1/admin/registry`), get active production model (`/v1/admin/registry/active`), promote a candidate (`/v1/admin/registry/promote`). Promotion requires passing the evaluation gate.

**admin.py** — Version and configuration introspection. Shows active component versions (`/v1/admin/versions`) and non-sensitive config (`/v1/admin/config`).

**metrics.py** — Prometheus metrics endpoint (`/metrics`). Serves `prometheus_client.generate_latest()` as plain text for scraping.

---

## `app/core/`

**config.py** — Pydantic Settings class loading environment variables. Covers generation backend, LLM connection, ChromaDB paths, embedding model, reranker backend, grounding thresholds, and environment name.

**logging.py** — Structured logging setup using structlog. Configures JSON output for production and human-readable console output for development.

**metrics.py** — Prometheus metric definitions: request counters, latency histograms, retrieval/generation latency, confidence score distribution, policy action counts, grounding ratio distribution, and build info.

**exceptions.py** — Custom exception types: `PolicyViolationError` (raised on injection detection or policy blocks) and `VerificationError` (raised on verification failures). Used by middleware for structured error responses.

**security.py** — Source filtering utilities. Provides functions to restrict retrieval results to approved source sets based on request parameters.

**auth.py** — API key-based authentication. Maps API keys to user IDs and roles (`viewer`, `admin`). Dev mode allows anonymous access as viewer. Designed as a swappable layer for JWT/OAuth integration.

**audit.py** — Append-only audit event logger. Records security-relevant events (policy decisions, admin operations, document lifecycle changes) to a JSONL file. Module-level singleton for easy import.

---

## `app/domain/`

**ports.py** — Protocol-based interfaces (ports) defining the contracts between business logic and infrastructure: `Embedder`, `VectorStore`, `Reranker`, `Generator`, `Verifier`, `DocumentRepository`. Services depend on these abstractions, enabling backend swaps and testing with fakes.

**models.py** — Pure domain value objects and enums: `DocumentStatus`, `JobStatus`, `JobType`, `PromotionStatus`, `CorpusVersion`, `IngestionRun`, `ModelRegistryEntry`. No infrastructure dependencies.

---

## `app/models/`

**api.py** — Pydantic request/response models for the REST API: `QueryRequest`, `QueryResponse`, `Citation`, and related schemas. Defines the external contract.

**domain.py** — Internal dataclasses used across services: `RetrievedChunk`, `GeneratedAnswer`, and other pipeline-internal value objects.

**enums.py** — `PolicyAction` enum governing the response gating decisions. `postcheck_response()` returns `ALLOW`, `ALLOW_WITH_WARNING`, or `ABSTAIN`; `REDACT` and `ESCALATE` are reserved for future policy rules, and `BLOCK` is emitted by `precheck_request()` on prompt-injection detection.

**jobs.py** — `Job` dataclass for async task orchestration. Tracks status, params, timestamps, retry count, result, and error. Supports dict serialization/deserialization.

---

## `app/services/`

**rag_service.py** — Main orchestration service. Drives the full request lifecycle: policy precheck, retrieval, reranking, prompt rendering, generation, verification, policy postcheck, citation attachment. Dependencies injected via constructor through domain ports.

**retrieval_service.py** — Search and evidence preparation layer. Runs vector search via the VectorStore port, applies ACL filtering (role-based), excludes revoked documents, and prepares context blocks for prompt rendering. Provides both async and sync search paths.

**embedding_service.py** — Sentence-transformers wrapper implementing the Embedder port. Lazy-loads the model on first use (~90MB for all-MiniLM-L6-v2). Thread-safe with a lock-protected singleton cache.

**vector_store.py** — ChromaDB implementation of the VectorStore port. Manages the embedded ChromaDB collection with persistent storage. Supports search, upsert, delete, count, and metadata updates.

**reranker_service.py** — Second-stage relevance scoring with two switchable backends: TF-IDF cosine similarity (default, zero model download) and cross-encoder (higher quality, requires model download). Provides both async and sync rerank paths.

**prompt_service.py** — YAML-based prompt template rendering. Loads versioned prompt templates from `ml/prompts/` and renders them with question and context variables using Jinja-style substitution.

**model_router.py** — Task-to-model routing. Maps task types (`text_qa`, `multimodal_qa`, `longform_reasoning`) to the appropriate model backend identifier. (`multimodal_qa` and `longform_reasoning` are scaffolding; no callers pass these task types yet.)

**generation_service.py** — Pluggable text generation with three backends: template (extractive QA, default, no LLM needed), Ollama, and OpenAI-compatible APIs. Template mode parses evidence blocks, scores sentences via TF-IDF, and composes grounded answers with citation markers. Falls back to template on LLM failure. Provides both async and sync generation paths.

**citation_service.py** — Source attribution. Attaches document IDs, titles, and content snippets to the response for transparency and traceability.

**policy_service.py** — Pre- and post-generation policy enforcement. Pre-check detects prompt injection patterns. Post-check enforces grounding support thresholds, returning ALLOW, ALLOW_WITH_WARNING, or ABSTAIN (postcheck); BLOCK raised by precheck.

**verification_service.py** — Grounding verification using TF-IDF sentence similarity. Compares answer sentences against retrieved evidence to compute a support ratio. Lightweight heuristic; interface supports future swap to NLI or claim-extraction verifiers.

**evaluation_service.py** — Benchmark harness for RAG pipeline quality. Runs golden QA datasets through the pipeline synchronously, computes grounded_support, citation_coverage, keyword_coverage, and avg_latency_ms metrics (unsupported_rate = 1 − grounded_support is included as a derived field; hallucination_rate is not a separately reported metric). Supports baseline comparison and promotion gate enforcement.

**job_service.py** — File-backed async job orchestration. Manages job lifecycle (pending, running, completed, failed, retrying) with persistent JSON storage. Interface supports migration to Redis/Celery.

**corpus_service.py** — Document lifecycle management. Tracks document status (active, superseded, revoked), corpus versions, and ingestion runs. Ensures revoked documents are excluded from retrieval.

**model_registry.py** — Lightweight local model lifecycle tracking. File-backed registry for tracking model bundles through promotion stages: candidate, shadow, canary, production, or rejected. Promotion requires passing the evaluation gate.

---

## `pipelines/`

**ingest_pipeline.py** — Document loading, chunking, embedding, and indexing pipeline. Reads markdown files from `data/sample_docs/`, splits into chunks, embeds via sentence-transformers, and upserts into ChromaDB. Records corpus versions and ingestion runs.

**run_evaluation.py** — Golden QA benchmark runner. Executes the evaluation service against `golden_qa_v1.json`, compares candidate metrics against the saved baseline, checks promotion gate thresholds, and saves passing candidates as the new baseline.

**run_finetune.py** — Finetune Lifecycle Stub (SIMULATED SFT by default). Exercises the orchestration around training — dataset validation, recipe parsing, checkpoint registration, post-training evaluation, promotion-gate enforcement — but the training step itself calls `_simulate_training()` and returns placeholder metrics. This is intentional: the file is a lifecycle contract, not a trainer. The integration point for a real GPU backend (SageMaker, Vertex AI, Ray Train, torchtune) is labelled inline.

---

## `ml/prompts/`

**grounded_answer.yaml** — Versioned prompt template for the grounded QA task. Defines system and user message templates with placeholders for question and evidence context. Instructs the model to answer only from provided evidence and refuse when evidence is insufficient.

---

## `data/`

**audit.jsonl** — Append-only audit log file. Each line is a JSON object recording a security-relevant event (policy decisions, admin operations, etc.).

**sample_docs/** — Seven sample SOP/policy/guide markdown documents used for development and testing: onboarding guide, acceptable use policy, incident response SOP, evidence handling SOP, access control SOP, data classification SOP, and change management SOP.

**golden_qa/** — Benchmark QA dataset (`golden_qa_v1.json`) with questions, expected sources, and expected answer keywords for evaluation.

**finetune/** — Fine-tuning sample data: `sample_recipe.yaml` (hyperparameter configuration) and `sample_dataset.json` (input/output training pairs). Note: `base_model: text-main` in `sample_recipe.yaml` is a project-wide demo placeholder — replace it with a real model identifier when connecting a real training backend.

---

## `infra/docker/`

**api.Dockerfile** — Multi-stage Docker build for the API service. Runs as a non-root user, installs dependencies from pyproject.toml, and starts uvicorn.

**worker.Dockerfile** — Docker build for the pipeline runner. Same base as the API but configured for running offline pipeline jobs (ingest, evaluation, fine-tuning).

---

## `infra/k8s/`

**namespace.yaml** — Kubernetes namespace definition (`llm-ops`) to isolate the platform resources.

**api-deployment.yaml** — Kubernetes Deployment for the API. Configures 2 replicas, CPU/memory resource limits, liveness/readiness probes pointing to health endpoints, and PVC mount for ChromaDB persistence.

**service.yaml** — ClusterIP Service exposing the API deployment on port 80 (targeting container port 8000). Internal cluster access only.

**configmap.yaml** — Kubernetes ConfigMap holding non-sensitive configuration: environment name, log level, generation backend, reranker backend, ChromaDB paths, embedding model, grounding threshold, and data directory.

**ingress.yaml** — Ingress resource for external access via `llm-ops.internal` hostname. Includes rate limiting (100 connections) and request body size limit (10MB) via nginx annotations. No `tls:` block is present — all traffic is plain HTTP. Add a `tls:` section and a cert-manager annotation before production use.

**pvc.yaml** — PersistentVolumeClaim (10Gi, ReadWriteOnce) for ChromaDB data persistence across pod restarts.

---

## `tests/`

**conftest.py** — Shared pytest fixtures: FastAPI test client, sample `RetrievedChunk` instances, and sample evidence text blocks used across multiple test files.

**test_health.py** — Tests for liveness and readiness probe endpoints, verifying correct status codes and response structure.

**test_query_api.py** — Integration tests for the `/v1/query` endpoint, covering normal queries, empty questions, and citation toggling.

**test_corpus_service.py** — Tests for corpus governance: document status tracking, revocation, and corpus version management.

**test_evaluation_service.py** — Tests for the benchmark harness: metric computation, baseline comparison, and promotion gate enforcement.

**test_failure_modes.py** — Tests verifying graceful degradation: empty vector store, missing documents, backend failures, and error response formatting.

**test_generation_service.py** — Tests for all generation backends: template extractive QA, prompt parsing, sentence scoring, and answer composition.

**test_ingest_pipeline.py** — Tests for the ingestion pipeline: document loading, chunking, embedding, and indexing into the vector store.

**test_job_service.py** — Tests for async job orchestration: job creation, status transitions, retry logic, and persistence.

**test_model_registry.py** — Tests for model lifecycle: registration, promotion stages, gate enforcement, and active model queries.

**test_policy_service.py** — Tests for pre- and post-generation policy checks: injection detection, grounding threshold enforcement, and policy action mapping.

**test_reranker_service.py** — Tests for both TF-IDF and cross-encoder reranking backends: score blending, ordering, and edge cases.

**test_retrieval_service.py** — Tests for vector search: ACL filtering, revoked document exclusion, source filtering, and context preparation.

**test_verification_service.py** — Tests for grounding verification: support ratio computation, sentence matching, and threshold behavior.

---

## Directory roles
- `app/` = online serving — request/response lifecycle, dependency injection, middleware
- `pipelines/` = long-running offline jobs — ingestion, evaluation, fine-tuning
- `infra/` = deployment — Docker builds, Kubernetes manifests, CI/CD
- `ml/` = versioned ML artifacts — prompt templates, model configs
- `data/` = development fixtures — sample docs, benchmark datasets, audit logs
- `docs/` = architecture and operations documentation
- `tests/` = 100 tests across 15 files

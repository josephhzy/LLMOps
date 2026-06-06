# 05 — Deployment and MLOps

## Environment separation
Use at least:
- dev
- staging
- prod

Better:
- sandbox
- dev
- eval
- staging
- prod

---

## CI Pipeline (`.github/workflows/ci.yml`)

The CI pipeline is defined in `.github/workflows/ci.yml` and runs on every push to `main` and on every pull request targeting `main`. It consists of four parallel jobs:

### Job 1: `lint`
Runs Ruff for both code style and formatting enforcement.
```yaml
steps:
  - uses: actions/checkout@v4
  - uses: actions/setup-python@v5
    with:
      python-version: "3.11"
  - run: pip install ruff
  - run: ruff check app/ pipelines/ tests/ benchmarks/       # Lint rules
  - run: ruff format --check app/ pipelines/ tests/ benchmarks/  # Format check (no auto-fix)
```

### Job 2: `test`
Installs the project with dev dependencies, runs pytest (excluding integration tests), collects coverage, and uploads to Codecov.
```yaml
steps:
  - uses: actions/checkout@v4
  - uses: actions/setup-python@v5
    with:
      python-version: "3.11"
      cache: pip                                 # Caches pip downloads between runs
  - run: pip install -e ".[dev]"
  - run: pytest -q -m "not integration" --tb=short --cov=app --cov=pipelines --cov-report=xml
  - uses: codecov/codecov-action@v4              # Upload coverage (non-blocking)
    if: always()
    with:
      file: ./coverage.xml
    continue-on-error: true
```

### Job 3: `typecheck`
Runs mypy for static type checking across the `app/` package. No `continue-on-error` — type errors block PR merges.
```yaml
steps:
  - uses: actions/checkout@v4
  - uses: actions/setup-python@v5
    with:
      python-version: "3.11"
      cache: pip
  - run: pip install -e ".[dev]"
  - run: mypy app/ --ignore-missing-imports
```

### Job 4: `docker`
Validates that the Docker Compose build succeeds (catches Dockerfile syntax errors, missing files, dependency issues).
```yaml
steps:
  - uses: actions/checkout@v4
  - run: docker compose build
```

---

## Docker Commands

### Build and run locally
```bash
# Build all images defined in docker-compose.yml
docker compose build

# Start the API service (detached)
docker compose up -d

# View logs
docker compose logs -f api

# Stop and remove containers
docker compose down

# Rebuild after code changes
docker compose build --no-cache && docker compose up -d
```

### Build individual images
```bash
# API image
docker build -f infra/docker/api.Dockerfile -t llm-ops-api:latest .

# Worker image (for pipeline jobs)
docker build -f infra/docker/worker.Dockerfile -t llm-ops-worker:latest .
```

### Run with environment overrides
```bash
# Use a real LLM backend
docker compose run -e GENERATION_BACKEND=ollama -e LLM_BASE_URL=http://host.docker.internal:11434 api
```

---

## CD pipeline (design)
No CD workflow is implemented in this demo; the following describes the intended production flow.

On merge to main:
- build images
- sign images
- deploy non-prod
- run smoke tests
- optionally launch benchmark suite

## Promotion gate
Promote only if:
- latency within target
- support / groundedness above threshold (default: 0.75) — hallucination rate is derived as 1 − grounded_support and is not a separate gate key
- citation coverage above threshold (default: 0.70)
- failure rate acceptable
- security checks pass

In the API path (`POST /v1/admin/registry/promote`), the gate is enforced by `ModelRegistry._check_promotion_gate` (app/services/model_registry.py), which hard-codes the thresholds inline. In the offline benchmark pipeline (`pipelines/run_evaluation.py`), `EvaluationService.check_promotion_gate()` applies the same thresholds defined in that file.

## Rollout strategy
1. benchmark gate
2. shadow traffic
3. canary 1%
4. canary 5%
5. canary 25%
6. full rollout
7. instant rollback on regression

## Kubernetes Deployment

The `infra/k8s/` directory contains example Kubernetes manifests:

```bash
# Apply all manifests
kubectl apply -f infra/k8s/namespace.yaml
kubectl apply -f infra/k8s/configmap.yaml
kubectl apply -f infra/k8s/pvc.yaml
kubectl apply -f infra/k8s/rbac.yaml
kubectl apply -f infra/k8s/api-deployment.yaml
kubectl apply -f infra/k8s/service.yaml
kubectl apply -f infra/k8s/ingress.yaml

# Verify deployment
kubectl get pods -n llm-ops
kubectl get svc -n llm-ops
```

> **Note:** `ingress.yaml` ships without a `tls:` section and serves traffic over plain HTTP. Configure cert-manager or supply a TLS secret before deploying outside a local cluster.

The deployment runs 2 replicas with CPU/memory resource limits, liveness/readiness probes, and a PVC for ChromaDB persistence.

# 07 — Operations Runbook

## Quick Reference Commands

### Health Checks
```bash
# Liveness probe — returns 200 if the process is running
curl http://localhost:8000/health/live

# Readiness probe — returns 200 if all dependencies (vector store, embedding model) are available
curl http://localhost:8000/health/ready
```

### Metrics
```bash
# Prometheus metrics endpoint — request counts, latency histograms, quality scores
curl http://localhost:8000/metrics

# Key metrics to watch:
#   llm_ops_requests_total — request volume by endpoint/status
#   llm_ops_request_duration_seconds — P50/P95/P99 latency
#   llm_ops_policy_action_total — ALLOW/ALLOW_WITH_WARNING/ABSTAIN/BLOCK counts
#   llm_ops_grounding_ratio — support ratio distribution
#   llm_ops_confidence_score — response confidence distribution
```

### Rollback
```bash
# Rollback to the previous deployment revision
kubectl rollout undo deployment/llm-ops-api -n llm-ops

# Rollback to a specific revision
kubectl rollout undo deployment/llm-ops-api -n llm-ops --to-revision=3

# Verify rollback status
kubectl rollout status deployment/llm-ops-api -n llm-ops
```

### View Logs
```bash
# Tail recent logs from all API pods
kubectl logs -l app=llm-ops-api -n llm-ops --tail=100

# Follow logs in real time
kubectl logs -l app=llm-ops-api -n llm-ops -f

# Logs from a specific pod
kubectl logs <pod-name> -n llm-ops --tail=200

# Local Docker Compose logs
docker compose logs -f api --tail=100
```

### Restart
```bash
# Rolling restart (zero-downtime with 2 replicas)
kubectl rollout restart deployment/llm-ops-api -n llm-ops

# Verify restart completes
kubectl rollout status deployment/llm-ops-api -n llm-ops

# Local Docker restart
docker compose restart api
```

### Corpus Operations
```bash
# Check corpus status
curl http://localhost:8000/v1/admin/corpus/status

# View active model version
curl http://localhost:8000/v1/admin/registry/active

# View component versions
curl http://localhost:8000/v1/admin/versions

# Trigger re-indexing
curl -X POST http://localhost:8000/v1/ingest/rebuild-index
```

---

## Typical incidents
### Sev 1
- API unavailable
- restricted data leak
- major wrong-answer incident
- model backend outage with no fallback

### Sev 2
- latency spike
- vector DB degradation
- canary regression

## Example response flow for hallucination spike
1. Check current metrics: `curl http://localhost:8000/metrics | grep grounding_ratio`
2. Identify latest release bundle: `curl http://localhost:8000/v1/admin/versions`
3. Compare model/prompt/retriever versions: `curl http://localhost:8000/v1/admin/registry`
4. Disable canary / rollback: `kubectl rollout undo deployment/llm-ops-api -n llm-ops`
5. Rerun golden benchmark: `python -m pipelines.run_evaluation`
6. Inspect unsupported-claim traces in structured logs:
   ```bash
   kubectl logs -l app=llm-ops-api -n llm-ops --tail=500 | grep policy_decision
   ```
7. If confirmed regression, keep rollback; if false alarm, re-deploy

## Example response flow for API unavailable (Sev 1)
1. Check pod status: `kubectl get pods -n llm-ops`
2. Check liveness: `curl http://localhost:8000/health/live`
3. Check readiness: `curl http://localhost:8000/health/ready`
4. View recent logs: `kubectl logs -l app=llm-ops-api -n llm-ops --tail=200`
5. If OOM or crash loop: check resource limits in `infra/k8s/api-deployment.yaml`
6. Restart: `kubectl rollout restart deployment/llm-ops-api -n llm-ops`

## Daily checks
- 5xx rate — `llm_ops_requests_total{status=~"5.."}`
- P95 latency — `histogram_quantile(0.95, llm_ops_request_duration_seconds_bucket)`
- No-answer rate — count of `llm_ops_policy_action_total{action="ABSTAIN"}`
- Policy block rate — count of `llm_ops_policy_action_total{action="BLOCK"}`
- GPU utilization (if using LLM backend)
- Vector DB health — `curl http://localhost:8000/health/ready`
- Queue backlog — `curl http://localhost:8000/v1/jobs`
- Index freshness — `curl http://localhost:8000/v1/admin/corpus/status`

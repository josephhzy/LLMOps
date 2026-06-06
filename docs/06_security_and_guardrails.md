# 06 — Security and Guardrails

## Threat model
Assume:
- prompt injection in documents
- unauthorized retrieval
- data exfiltration attempts
- jailbreak prompts
- unsafe multimodal inputs
- secret leakage in logs
- unsupported claims in outputs

## Controls by layer
### Request layer
- auth (X-API-Key via `get_current_user`; applied to mutation endpoints — query, ingest, register, promote, revoke; `/metrics` and `/v1/admin/versions|config` use `get_current_user` — anonymous viewer access allowed when env=dev, API key required otherwise)
- RBAC (`require_admin` guard on register/promote/revoke; read endpoints use viewer-or-anonymous default)
- rate limiting (nginx ingress annotation only; see infra/k8s/ingress.yaml — not enforced in the single-node demo)
- request classification

### Retrieval layer
- ACL filtering
- source allowlists
- document classification tags
- quarantine for suspicious corpora (planned)

### Prompt layer
- evidence-only system prompts
- context isolation
- prompt-injection heuristics

### Response layer
- support verification
- abstention
- redaction
- escalation

## Important principle
In regulated systems, abstention — returning no answer when grounding support is insufficient — is an intended and valid response.

# 09 — Threat Model

## Overview

This document maps the attack surfaces of the LLM Ops platform, identifies threats specific to RAG systems in regulated or compliance-sensitive contexts, and documents mitigations implemented or planned.

## Attack Surface Matrix

| # | Attack Surface | Threat | Severity | Mitigation | Status |
|---|---------------|--------|----------|------------|--------|
| T1 | User query input | Prompt injection | High | Regex scaffolding in PolicyService.precheck_request; measured recall 0/15 — not a deployed guardrail (see docs/INJECTION_EVAL.md) | Placeholder |
| T2 | User query input | PII leakage via query | Medium | PII masking hook interface in PolicyService | Interface only |
| T3 | Retrieval results | Context poisoning via malicious docs | High | Document classification + ACL filtering + corpus governance | Implemented |
| T4 | Retrieval results | ACL bypass (viewer sees restricted) | High | Role-based ACL filter in RetrievalService.apply_acl_filter | Implemented |
| T5 | Generated response | Hallucinated content | High | Grounding verification + policy postcheck (ABSTAIN on low support) | Implemented |
| T6 | Generated response | PII in response | Medium | Response PII masking hook | Planned |
| T7 | Model backend | Model exfiltration via prompt | Low | No model weights served; API-only access pattern | By design |
| T8 | Admin endpoints | Unauthorized corpus changes | High | `require_admin` dependency enforced on /corpus/revoke, /registry/register, /registry/promote (corpus.py, registry.py); covered by TestAdminGuard | Implemented |
| T9 | Ingestion pipeline | Malicious document injection | Medium | Corpus governance with document status tracking + revocation | Implemented |
| T10 | Audit trail | Tampering with logs | Medium | Append-only JSONL audit log; immutable store in production | File-backed |
| T11 | Model promotion | Promoting undertested models | Medium | Evaluation gate required for production promotion | Implemented |
| T12 | API endpoints | DoS via expensive queries | Low | Rate limiting via ingress annotation; per-query timeout | Partial |

## Classification Enforcement

Documents are classified at ingestion time via YAML frontmatter:

| Classification | Viewer Access | Admin Access | Handling |
|---------------|--------------|-------------|---------|
| public | Yes | Yes | No restrictions |
| internal | Yes | Yes | Default tier |
| restricted | No | Yes | Filtered by ACL before prompt construction |

Classification is enforced at retrieval time, not generation time. This prevents restricted content from ever entering the LLM prompt for unauthorized users.

## Prompt Injection Defense

The PolicyService contains a regex pre-check that scans for known injection phrases. It is scaffolding (0/15 adversarial recall); a classifier-based detector is the planned replacement:

> **Measured recall: 0/15 — every adversarial prompt slipped through. This is a placeholder interface, not a deployed guardrail. See [docs/INJECTION_EVAL.md](INJECTION_EVAL.md).**

- Direct instruction override ("ignore previous instructions")
- Role assumption ("you are now a", "act as if")
- System prompt manipulation ("<system>", "system prompt:")
- Instruction injection ("new instructions:")

Limitations:
- Recall is 0/15 on the hand-curated adversarial set (see docs/INJECTION_EVAL.md) — all 15 adversarial prompts evaded detection; this layer catches nothing in practice
- No semantic injection detection (would require a classifier model)
- No output-side injection detection (checking if the model was successfully manipulated)

## Document Lifecycle Security

The corpus governance system provides:

1. **Revocation**: Documents can be revoked with reason tracking. Revoked documents are excluded from retrieval via metadata filtering.
2. **Supersession**: Old document versions are marked as superseded when replaced.
3. **Ingestion tracking**: Each ingestion run is tracked with run ID and corpus version.
4. **Audit trail**: All corpus changes are logged to the audit system.

## Recommendations for Production Hardening

1. Rotate to per-user API keys stored in a secrets manager — current dev keys are static and shared (dev-viewer-key / dev-admin-key are intentional demo keys, not for production)
2. Replace static X-API-Key auth with JWT or OAuth 2.0 backed by an identity provider for per-user accountability and token revocation
3. Deploy PII detection model for both queries and responses
4. Move audit log to immutable store (append-only S3, Elasticsearch)
5. Add semantic prompt injection classifier (current regex pre-check has 0/15 adversarial recall)
6. Add network policies to restrict model backend access
7. Enable TLS for all internal communication
8. Implement prompt template locking (prevent runtime modification)
9. Add response redaction for classification boundary violations

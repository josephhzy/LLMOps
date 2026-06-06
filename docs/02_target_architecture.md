# 02 — Target Architecture

## High-level architecture

Components marked `← planned` are not yet implemented. Everything else is present in `app/`.

```text
[Apps / Internal Portals / Bots]
             |
             v
      [API Gateway / Auth]
             |
             v
      [FastAPI Serving Layer]
             |
     +-------+--------+
     |                |
     v                v
[Policy Guardrails] [Request Logging]
     |
     v
[Retrieval Orchestrator] --> [Vector DB]
     |                         |
     |                         v
     +--> [Metadata / ACL] -> [ChromaDB metadata]
     |
     v
  [Reranker]
     |
     v
[Prompt Builder]
     |
     v
 [Model Router] --> [Text LLM Backend]
     |             [Multimodal Backend]  ← planned Phase 5; not yet implemented
     v
[Verification + Citations]
     |
     v
[Response Policy Gate]
     |
     v
[Final Response + Trace ID]
```

## Offline plane
```text
[Documents] -> [Ingestion] -> [Chunking] -> [Embedding] -> [Index Build]
[Datasets] -> [Fine-tuning] -> [Evaluation] -> [Registry] -> [Promotion]
[Shadow Logs + Golden Sets] -> [Benchmark Harness] -> [Release Gates]
```

## Request lifecycle
1. Authenticate request
2. Pre-policy check
3. Retrieve candidates
4. Apply ACL/source filters
5. Rerank
6. Build grounded prompt
7. Route to best model
8. Generate answer
9. Verify support
10. Apply response policy
11. Persist trace
12. Return answer with citations

## Common failure points
- bad chunking
- no ACL filter before prompt assembly
- no benchmark suite
- prompt changes without versioning
- no canary or rollback path

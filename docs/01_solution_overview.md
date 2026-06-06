# 01 — Solution Overview

## What problem this project solves
Application teams want to use LLMs in real products, but production breaks when teams only think about prompting.

Real production problems:
- hallucination
- stale or weak retrieval
- hidden prompt regressions
- failing deployment pipelines
- GPU contention
- poor observability
- weak access control
- no rollback discipline

## What we are building
A reference architecture demonstrating 5 major subsystems:
1. Serving layer
2. Retrieval layer
3. Generation layer
4. Evaluation and monitoring layer
5. Fine-tuning / model lifecycle layer

## Example use cases
- policy / SOP assistant
- incident playbook assistant
- internal knowledge search
- multimodal case-file assistant (planned — Phase 5)

## Design separations

The architecture separates:
- ingestion vs serving
- training vs inference
- policy vs prompts
- evaluation vs deployment
- model selection vs application code

These separations keep the system maintainable.

# 04 — Function Reference

## API layer
### `create_app()`
Creates FastAPI app, middleware, routes, startup hooks.

### `healthcheck()`
Confirms the process is alive.

### `readycheck()`
Confirms dependencies are reachable.

### `query_rag(request)`
Thin route that delegates to orchestration.

## Orchestration
### `RAGService.answer()`
Runs the full pipeline:
1. request validation
2. policy precheck
3. retrieve
4. rerank
5. prompt render
6. generation
7. verification
8. response policy
9. citation formatting
10. trace creation

### `RAGService._compute_confidence()`
Combines retrieval + support signals.

### `RAGService._generate_trace_id()`
Creates unique audit trace IDs.

## Retrieval
### `RetrievalService.search()`
First-stage search into corpus.

### `RetrievalService.apply_acl_filter()`
Removes unauthorized chunks before prompting.

### `RetrievalService.prepare_context()`
Turns chunks into prompt-ready evidence blocks.

## Reranking
### `RerankerService.rerank()`
Improves ordering of retrieved chunks.

## Prompting
### `PromptService.load_template()`
Loads versioned prompt config.

### `PromptService.render_grounded_prompt()`
Builds the final grounded prompt.

## Generation
### `ModelRouter.route()`
Chooses the correct model for task type.

### `GenerationService.generate()`
Calls backend and normalizes output.

## Guardrails and verification
### `VerificationService.verify_grounding()`
Checks support of output against evidence.

### `CitationService.attach_citations()`
Formats citations for response.

### `PolicyService.precheck_request()`
Blocks obvious injection or disallowed requests.

### `PolicyService.postcheck_response()`
Decides allow, allow-with-warning, or abstain (based on grounding support ratio).

## Evaluation
### `EvaluationService.run_benchmark()`
Runs benchmark suite.

### `EvaluationService.compare_runs()`
Compares candidate vs baseline.

### `EvaluationService.check_promotion_gate()`
Checks threshold-based promotion criteria.

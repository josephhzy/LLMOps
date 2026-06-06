"""Evaluation service — benchmark harness for RAG pipeline quality.

Runs golden QA datasets through the pipeline, computes aggregate metrics,
compares candidates against baselines, and enforces promotion gates.

This service is fully synchronous. It drives each RAG stage directly
(retrieval, reranking, generation, verification, policy, citation)
without going through the async RAGService.answer() path. This avoids
the hazard of calling asyncio.run() inside an already-running event loop
and keeps the benchmark harness independent of the serving layer.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from app.core.logging import get_logger

logger = get_logger(__name__)


class EvaluationService:
    """Benchmark harness for measuring pipeline quality."""

    def run_benchmark(self, benchmark_name: str, candidate_version: str) -> dict:
        """Run benchmark suite against a golden QA dataset.

        Loads questions from data/golden_qa/{benchmark_name}.json,
        runs each through the RAG pipeline, and computes aggregate metrics.
        """
        dataset_path = Path(f'data/golden_qa/{benchmark_name}.json')
        if not dataset_path.exists():
            logger.warning('benchmark_no_dataset', path=str(dataset_path))
            return {
                'benchmark_name': benchmark_name,
                'candidate_version': candidate_version,
                'status': 'no_dataset',
                'grounded_support': 0.0,
                'citation_coverage': 0.0,
                'unsupported_rate': 1.0,
            }

        dataset = json.loads(dataset_path.read_text())
        logger.info('benchmark_start', name=benchmark_name, num_questions=len(dataset))

        results = []
        for item in dataset:
            result = self._evaluate_single(item)
            results.append(result)

        n = len(results) or 1
        avg_support = sum(r['supported_ratio'] for r in results) / n
        avg_citation = sum(r['citation_hit'] for r in results) / n
        avg_keyword = sum(r['keyword_coverage'] for r in results) / n
        avg_latency = sum(r['latency_ms'] for r in results) / n

        metrics = {
            'benchmark_name': benchmark_name,
            'candidate_version': candidate_version,
            'num_questions': len(dataset),
            'grounded_support': round(avg_support, 4),
            'citation_coverage': round(avg_citation, 4),
            'keyword_coverage': round(avg_keyword, 4),
            'unsupported_rate': round(
                1.0 - avg_support, 4
            ),  # fraction of sentences with low TF-IDF overlap vs. retrieved evidence; not a factual entailment check
            'avg_latency_ms': round(avg_latency, 2),
        }

        logger.info('benchmark_complete', **metrics)
        return metrics

    def _evaluate_single(self, item: dict) -> dict:
        """Evaluate a single QA pair synchronously.

        Drives each pipeline stage directly using synchronous wrappers,
        avoiding any asyncio.run() or event loop manipulation. This is
        safe to call from any context (sync, async, inside an existing loop).
        """
        from app.models.api import Citation, QueryRequest
        from app.models.enums import PolicyAction
        from app.services.citation_service import CitationService
        from app.services.generation_service import GenerationService
        from app.services.policy_service import PolicyService
        from app.services.prompt_service import PromptService
        from app.services.reranker_service import RerankerService
        from app.services.retrieval_service import RetrievalService
        from app.services.verification_service import VerificationService

        question = item['question']
        expected_sources = set(item.get('expected_sources', []))
        expected_keywords = item.get('expected_answer_contains', [])
        role = item.get('role', 'viewer')

        retrieval = RetrievalService()
        reranker = RerankerService()
        prompt_svc = PromptService()
        generation = GenerationService()
        verification = VerificationService()
        policy = PolicyService()
        citation_svc = CitationService()

        request = QueryRequest(question=question)

        start = time.perf_counter()

        # Drive the pipeline synchronously — mirrors RAGService.answer()
        # but calls each stage's sync internals directly.
        policy.precheck_request(request)
        chunks = retrieval.search_sync(question, request.top_k, role, request.sources or [])
        ranked = reranker.rerank_sync(question, chunks)
        context = retrieval.prepare_context(ranked)
        prompt = prompt_svc.render_grounded_prompt(question, context)
        generated = generation.generate_sync(prompt=prompt, task_type='text_qa')
        verification_result = verification.verify_grounding(generated.text, ranked)
        policy_action = policy.postcheck_response(verification_result['supported_ratio'])

        confidence = round(
            (0.4 * max((c.score for c in ranked), default=0.0)) + (0.6 * verification_result['supported_ratio']),
            4,
        )
        citations = [Citation(**c) for c in citation_svc.attach_citations(ranked)]
        answer = (
            generated.text
            if policy_action not in {PolicyAction.ABSTAIN, PolicyAction.BLOCK}
            else 'I do not have enough grounded evidence to answer reliably.'
        )

        latency = (time.perf_counter() - start) * 1000

        returned_sources = {c.doc_id for c in citations}
        citation_hit = len(returned_sources & expected_sources) / max(len(expected_sources), 1)

        answer_lower = answer.lower()
        keyword_hits = sum(1 for kw in expected_keywords if kw.lower() in answer_lower)
        keyword_coverage = keyword_hits / max(len(expected_keywords), 1)

        return {
            'question': question,
            'supported_ratio': verification_result['supported_ratio'],
            'confidence': confidence,
            'citation_hit': citation_hit,
            'keyword_coverage': keyword_coverage,
            'policy_action': policy_action.value,
            'latency_ms': latency,
        }

    def compare_runs(self, baseline: dict, candidate: dict) -> dict:
        """Compare candidate against baseline with detail on improvements and regressions."""
        compare_keys = ['grounded_support', 'citation_coverage', 'unsupported_rate']
        improvements = {}
        regressions = {}

        for key in compare_keys:
            baseline_val = baseline.get(key, 0)
            candidate_val = candidate.get(key, 0)
            delta = round(candidate_val - baseline_val, 4)

            if key == 'unsupported_rate':
                if delta < 0:
                    improvements[key] = delta
                elif delta > 0:
                    regressions[key] = delta
            else:
                if delta > 0:
                    improvements[key] = delta
                elif delta < 0:
                    regressions[key] = delta

        return {
            'candidate_beats_baseline': candidate.get('grounded_support', 0) >= baseline.get('grounded_support', 0),
            'improvements': improvements,
            'regressions': regressions,
        }

    def check_promotion_gate(self, metrics: dict, thresholds: dict) -> bool:
        """Return True only if all required thresholds are met."""
        return all(metrics.get(k, 0) >= v for k, v in thresholds.items())

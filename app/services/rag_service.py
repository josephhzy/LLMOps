"""RAG orchestration service.

Accepts dependencies via constructor injection through domain ports.
Routes construct the service graph via the factory in dependencies.py.
"""

from __future__ import annotations

import hashlib
import uuid

from app.core.audit import audit
from app.core.config import settings
from app.core.logging import get_logger
from app.core.metrics import CONFIDENCE_SCORE
from app.domain.ports import Generator, Reranker, Verifier
from app.models.api import Citation, QueryRequest, QueryResponse
from app.models.enums import PolicyAction
from app.services.citation_service import CitationService
from app.services.generation_service import GenerationService
from app.services.policy_service import PolicyService
from app.services.prompt_service import PromptService
from app.services.reranker_service import RerankerService
from app.services.retrieval_service import RetrievalService
from app.services.verification_service import VerificationService

logger = get_logger(__name__)


class RAGService:
    """Main orchestration service.

    This is the heart of the online system.
    Dependencies are injected via constructor — services depend on
    ports (interfaces), enabling testing with fakes and swapping backends.
    """

    def __init__(
        self,
        retrieval: RetrievalService | None = None,
        reranker: Reranker | None = None,
        prompt: PromptService | None = None,
        generation: Generator | None = None,
        citation: CitationService | None = None,
        policy: PolicyService | None = None,
        verification: Verifier | None = None,
        shadow_verifier: Verifier | None = None,
    ) -> None:
        self.retrieval = retrieval or RetrievalService()
        self.reranker = reranker or RerankerService()
        self.prompt = prompt or PromptService()
        self.generation = generation or GenerationService()
        self.citation = citation or CitationService()
        self.policy = policy or PolicyService()
        self.verification = verification or VerificationService()
        # Captured once at construction for audit-trail tagging. These are the
        # configured versions of the versioned artefacts (prompt, policy)
        # that the service is running under — stamped into every
        # `query_result` event so replay can join back to the exact config.
        self._settings = settings

        # Shadow-mode verifier (defaults to NLI when the setting flag is on).
        # Runs in parallel with the primary verifier; its score is logged
        # to the audit event but does NOT affect the policy decision. This
        # lets us collect disagreement statistics without risking a gate
        # flip before the eval is complete. See docs/VERIFICATION_UPGRADE.md.
        self.shadow_verifier = shadow_verifier
        if self.shadow_verifier is None and self._settings.nli_shadow_enabled:
            try:
                from app.verification.nli_verifier import NLIVerifier

                self.shadow_verifier = NLIVerifier(
                    model_name=self._settings.nli_model_name,
                    entailment_threshold=self._settings.nli_entailment_threshold,
                )
                # Warm up eagerly so the first request doesn't pay model-load cost.
                # If warmup fails the verifier caches the error and returns a
                # sentinel dict on verify_grounding().
                self.shadow_verifier.warmup()
            except Exception as exc:
                logger.warning('nli_shadow_init_failed', error=str(exc))
                self.shadow_verifier = None

    async def answer(self, request: QueryRequest, role: str = 'viewer', user_id: str = 'anonymous') -> QueryResponse:
        """Run the full request lifecycle end to end.

        Args:
            request: The query request (question, top_k, etc.).
            role: Authenticated role from the auth layer. Never from request body.
            user_id: Authenticated user ID from the auth layer.
        """
        trace_id = self._generate_trace_id()
        log = logger.bind(trace_id=trace_id, user_id=user_id, role=role)

        log.info('query_start', question_length=len(request.question))
        audit.log_event(
            'query',
            user_id,
            'query',
            details={
                'question_length': len(request.question),
                'trace_id': trace_id,
            },
        )
        self.policy.precheck_request(request)

        chunks = await self.retrieval.search(request.question, request.top_k, role, request.sources or [])
        log.info('retrieval_complete', num_chunks=len(chunks))

        ranked = await self.reranker.rerank(request.question, chunks)
        context = self.retrieval.prepare_context(ranked)
        prompt = self.prompt.render_grounded_prompt(request.question, context)

        generated = await self.generation.generate(prompt=prompt, task_type='text_qa')
        log.info('generation_complete', model=generated.model_version, tokens_out=generated.tokens_out)

        verification = self.verification.verify_grounding(generated.text, ranked)
        policy_action = self.policy.postcheck_response(verification['supported_ratio'])
        log.info('policy_decision', action=policy_action.value, support_ratio=verification['supported_ratio'])

        # Shadow-mode verifier runs in parallel. Its output is logged and
        # attached to the audit event but never influences `policy_action`.
        # A disagreement is any case where the shadow verifier would have
        # chosen a different policy action than the primary gate did.
        shadow_result: dict | None = None
        if self.shadow_verifier is not None:
            try:
                shadow_result = self.shadow_verifier.verify_grounding(generated.text, ranked)
                log.info(
                    'shadow_verification',
                    verifier=shadow_result.get('verifier'),
                    shadow_support_ratio=shadow_result.get('supported_ratio'),
                    label_distribution=shadow_result.get('label_distribution'),
                )
            except Exception as exc:
                log.warning('shadow_verification_failed', error=str(exc))
                shadow_result = {'verifier': 'nli_error', 'error': str(exc)}

        confidence = self._compute_confidence(
            max((c.score for c in ranked), default=0.0),
            verification['supported_ratio'],
        )
        CONFIDENCE_SCORE.observe(confidence)
        citations = [Citation(**c) for c in self.citation.attach_citations(ranked)] if request.enable_citations else []
        answer = (
            generated.text
            if policy_action not in {PolicyAction.ABSTAIN, PolicyAction.BLOCK}
            else 'I do not have enough grounded evidence to answer reliably.'
        )

        # Emit a `query_result` audit event so replay_audit.py can reconstruct
        # what happened for a given trace_id without touching raw PII.
        # Deliberately excluded: raw question text, raw answer text. Only a
        # truncated SHA-256 of the answer is logged so the same answer can be
        # identified without revealing its content.
        audit_details = {
            'trace_id': trace_id,
            'retrieved_chunk_ids': [c.chunk_id for c in ranked],
            'retrieved_doc_ids': sorted({c.doc_id for c in ranked}),
            'model_version': generated.model_version,
            'prompt_version': settings.prompt_version,
            'policy_version': settings.policy_version,
            'retriever_version': settings.retriever_version,
            'tokens_in': generated.tokens_in,
            'tokens_out': generated.tokens_out,
            'supported_ratio': round(verification['supported_ratio'], 4),
            'policy_action': policy_action.value,
            'confidence': confidence,
            'answer_hash': hashlib.sha256(answer.encode('utf-8')).hexdigest()[:16],
            'answer_length': len(answer),
            'citation_count': len(citations),
        }
        if shadow_result is not None:
            # Shadow fields are flat to keep the audit schema grep-able.
            audit_details['shadow_verifier'] = shadow_result.get('verifier')
            audit_details['shadow_supported_ratio'] = round(float(shadow_result.get('supported_ratio', 0.0)), 4)
            audit_details['shadow_label_distribution'] = shadow_result.get('label_distribution')

        audit.log_event(
            'query_result',
            user_id,
            'query_result',
            target=trace_id,
            outcome=policy_action.value,
            details=audit_details,
        )

        return QueryResponse(
            answer=answer,
            confidence=confidence,
            citations=citations,
            trace_id=trace_id,
            policy_action=policy_action.value,
        )

    def _compute_confidence(self, retrieval_score: float, verification_score: float) -> float:
        """Simple combined confidence score."""
        return round((0.4 * retrieval_score) + (0.6 * verification_score), 4)

    def _generate_trace_id(self) -> str:
        """Create unique trace ID for auditability."""
        return f'trace-{uuid.uuid4().hex[:16]}'

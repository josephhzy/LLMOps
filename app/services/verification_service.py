"""Verification service — lightweight grounding support heuristic.

IMPORTANT: This is NOT a factual entailment checker. It measures vocabulary
overlap via TF-IDF cosine similarity as a proxy for evidence support.
It cannot detect contradictions, numerical errors, or semantic inversions.

Interface is designed for future swap to NLI, claim-extraction, or
citation-span verifiers via the Verifier port.
"""

from __future__ import annotations

import re

from app.core.config import settings
from app.core.logging import get_logger
from app.core.metrics import GROUNDING_RATIO
from app.models.domain import RetrievedChunk

logger = get_logger(__name__)


class VerificationService:
    """Lightweight grounding support heuristic using TF-IDF similarity.

    Limitations:
    - Measures word overlap, not semantic entailment
    - Cannot detect contradictions with similar vocabulary
    - Cannot verify numerical claims
    - Threshold tuning affects precision/recall tradeoff
    """

    def check_support(self, answer: str, chunks: list[RetrievedChunk]) -> dict:
        """Compute evidence support ratio.

        For each sentence in the answer, finds the max TF-IDF cosine
        similarity against all chunk contents. A sentence is "supported"
        if similarity >= grounding_threshold.

        Returns:
            dict with supported_ratio, sentence_verdicts, and num_claims.
        """
        if not answer or not answer.strip():
            return {'supported_ratio': 0.0, 'sentence_verdicts': [], 'num_claims': 0}

        if not chunks:
            return {'supported_ratio': 0.0, 'sentence_verdicts': [], 'num_claims': 0}

        sentences = self._split_sentences(answer)
        if not sentences:
            return {'supported_ratio': 0.0, 'sentence_verdicts': [], 'num_claims': 0}

        evidence_texts = [c.content for c in chunks]
        threshold = settings.grounding_threshold

        verdicts = self._compute_verdicts(sentences, evidence_texts, threshold)
        supported_count = sum(1 for v in verdicts if v['supported'])
        ratio = round(supported_count / len(verdicts), 4) if verdicts else 0.0
        GROUNDING_RATIO.observe(ratio)

        logger.info(
            'grounding_check',
            supported=supported_count,
            total=len(verdicts),
            ratio=ratio,
        )

        return {
            'supported_ratio': ratio,
            'sentence_verdicts': verdicts,
            'num_claims': len(verdicts),
        }

    # Backward-compatible alias
    verify_grounding = check_support

    def _split_sentences(self, text: str) -> list[str]:
        """Split text into sentences, filtering out short fragments."""
        clean = re.sub(r'\[\d+\]', '', text)
        parts = re.split(r'(?<=[.!?])\s+', clean)
        return [s.strip() for s in parts if len(s.strip()) > 15]

    def _compute_verdicts(
        self,
        sentences: list[str],
        evidence_texts: list[str],
        threshold: float,
    ) -> list[dict]:
        """Score each sentence against evidence corpus."""
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity

        all_texts = sentences + evidence_texts
        vectorizer = TfidfVectorizer(stop_words='english')
        try:
            tfidf_matrix = vectorizer.fit_transform(all_texts)
        except ValueError:
            return [{'sentence': s, 'max_similarity': 0.0, 'supported': False} for s in sentences]

        sentence_vecs = tfidf_matrix[: len(sentences)]
        evidence_vecs = tfidf_matrix[len(sentences) :]

        sim_matrix = cosine_similarity(sentence_vecs, evidence_vecs)

        verdicts = []
        for i, sentence in enumerate(sentences):
            max_sim = float(sim_matrix[i].max()) if sim_matrix[i].size > 0 else 0.0
            verdicts.append(
                {
                    'sentence': sentence,
                    'max_similarity': round(max_sim, 4),
                    'supported': max_sim >= threshold,
                }
            )

        return verdicts

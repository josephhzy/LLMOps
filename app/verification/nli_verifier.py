"""NLI-based grounding verifier — shadow-path implementation.

Replaces the TF-IDF overlap heuristic in `VerificationService` with a
cross-encoder NLI model that scores entailment between each claim
(answer sentence) and its cited evidence chunk.

Status: implemented but NOT wired into the default request path. Runs
alongside TF-IDF as a shadow for comparison on the golden QA set —
disagreements are logged to `evaluation/nli_shadow_results.json`. Default
verifier remains TF-IDF until the adversarial eval set grows large
enough to justify the cross-encoder forward-pass cost on every request.

Lazy-loads the model on first `verify_grounding()` call (or explicit
`warmup()`). If the download or load fails (no internet, corrupt cache,
torch missing), the verifier degrades gracefully: `verify_grounding()`
returns a sentinel dict with `verifier='nli_unavailable'` and the
caller can fall back to the TF-IDF path.

Implements the `Verifier` port so the swap is one line in
`app/api/dependencies.py` once the evaluation justifies it.
"""

from __future__ import annotations

import re
from typing import Any, Literal

from app.core.logging import get_logger

logger = get_logger(__name__)

EntailmentLabel = Literal['entailment', 'neutral', 'contradiction']

# Fixed label index for `cross-encoder/nli-deberta-v3-base`.
# Verified against `model.config.id2label` at load time — if it changes,
# `_load_model()` will warn rather than silently mis-score.
_EXPECTED_ID2LABEL = {0: 'contradiction', 1: 'entailment', 2: 'neutral'}


class NLIVerifier:
    """Cross-encoder NLI verifier.

    Design:
    - Split the answer into sentence-level *claims*.
    - For each claim, score entailment against every retrieved chunk
      (the *premise*), take the max entailment score across chunks.
    - Report per-claim verdict (entailment / neutral / contradiction)
      and aggregate `supported_ratio` (fraction of claims whose best
      chunk entails them above `entailment_threshold`).

    Contrast with the TF-IDF verifier which only reports a scalar
    overlap score — NLI gives a three-class distribution, which is
    what production RAG systems publish.
    """

    def __init__(
        self,
        model_name: str = 'cross-encoder/nli-deberta-v3-base',
        entailment_threshold: float = 0.70,
        device: str = 'cpu',
        max_length: int = 256,
        fallback_model_name: str | None = 'cross-encoder/nli-MiniLM2-L6-H768',
    ) -> None:
        self.model_name = model_name
        self.entailment_threshold = entailment_threshold
        self.device = device
        self.max_length = max_length
        # Smaller/faster fallback used when the primary model cannot be
        # downloaded or loaded (e.g. air-gapped CI, corrupt HF cache).
        # Set to None to disable the fallback and fail fast.
        self.fallback_model_name = fallback_model_name
        self._model: Any = None
        self._load_error: str | None = None
        self._id2label: dict[int, str] = dict(_EXPECTED_ID2LABEL)

    def _try_load(self, model_name: str):
        """Attempt to construct a CrossEncoder for `model_name`.

        Returns the loaded model on success, or None on any failure.
        Records the failure on `self._load_error` so callers can surface
        a single aggregated message after the fallback chain runs.
        """
        try:
            from sentence_transformers import CrossEncoder
        except ImportError as exc:  # pragma: no cover - defensive
            self._load_error = f'sentence_transformers not installed: {exc}'
            logger.warning('nli_load_failed', model=model_name, error=self._load_error)
            return None
        try:
            return CrossEncoder(
                model_name,
                device=self.device,
                max_length=self.max_length,
            )
        except Exception as exc:  # broad on purpose — network/cache failures
            self._load_error = f'failed to load NLI model {model_name!r}: {type(exc).__name__}: {exc}'
            logger.warning('nli_load_failed', model=model_name, error=self._load_error)
            return None

    def _load_model(self) -> bool:
        """Lazy-load the cross-encoder. Returns True on success.

        Tries the primary model first. On failure, falls back to
        `self.fallback_model_name` if set. Stores the last load error
        on `self._load_error` so callers can surface a clean message
        instead of crashing. Safe to call multiple times — no-op once
        loaded (or once the final load error has been cached).
        """
        if self._model is not None:
            return True
        if self._load_error is not None and self.fallback_model_name is None:
            return False

        model = self._try_load(self.model_name)
        if model is None and self.fallback_model_name:
            logger.info(
                'nli_falling_back_to_smaller_model',
                primary=self.model_name,
                fallback=self.fallback_model_name,
            )
            fallback = self._try_load(self.fallback_model_name)
            if fallback is not None:
                # Record which model we actually loaded so downstream
                # consumers see the honest model name, not the requested one.
                self.model_name = self.fallback_model_name
                model = fallback
                self._load_error = None
            else:
                # Both models failed; clear the fallback so the early-exit
                # guard short-circuits all future calls instead of retrying.
                self.fallback_model_name = None
        if model is None:
            return False
        self._model = model

        # Validate label mapping. Different HF revisions have flipped
        # the id2label in the past; pick up whatever the loaded model
        # reports so scoring stays correct.
        try:
            hf_id2label = self._model.model.config.id2label
            self._id2label = {int(k): str(v).lower() for k, v in hf_id2label.items()}
            if self._id2label != _EXPECTED_ID2LABEL:
                logger.warning(
                    'nli_label_mapping_changed',
                    expected=_EXPECTED_ID2LABEL,
                    actual=self._id2label,
                )
        except Exception:  # pragma: no cover - id2label not exposed
            logger.info('nli_label_mapping_unavailable_using_default')
        return True

    def warmup(self) -> None:
        """Pre-load the model so the first real request doesn't pay the cost."""
        self._load_model()

    def is_available(self) -> bool:
        """True if the model is loaded (or loadable)."""
        if self._model is not None:
            return True
        return self._load_model()

    def verify_grounding(self, answer, chunks=None) -> dict:
        """Score entailment between answer/claim text and evidence.

        Two call shapes supported:

        1. ``verify_grounding(claim: str, evidence: str) -> dict`` — the
           primitive pair-level form. Returns
           ``{"entailment": float, "neutral": float,
           "contradiction": float, "verified": bool}``. ``verified`` is
           ``True`` when ``P(entailment)`` exceeds
           ``self.entailment_threshold``.

        2. ``verify_grounding(answer: str, chunks: list[RetrievedChunk])
           -> dict`` — the orchestrated form used by the RAG pipeline.
           Splits the answer into sentence-sized claims, scores each
           one against every chunk, and returns the richer
           ``{supported_ratio, num_claims, sentence_verdicts,
           label_distribution, verifier, model}`` shape documented in
           the module docstring.

        The shape is dispatched on whether ``chunks`` is a string (form
        1) or a list (form 2). When the model cannot be loaded, form 2
        returns a sentinel with ``verifier='nli_unavailable'`` (so the
        RAG orchestrator can degrade gracefully), while form 1 is
        delegated to ``verify_pair`` which raises ``NotImplementedError``
        — external callers should not silently mistake a missing model
        for a real neutral verdict.
        """
        if isinstance(chunks, str):
            # Form 1: (claim: str, evidence: str) — primitive pair-level.
            return self.verify_pair(answer, chunks)

        if not self._load_model():
            return {
                'supported_ratio': 0.0,
                'num_claims': 0,
                'sentence_verdicts': [],
                'label_distribution': {'entailment': 0, 'neutral': 0, 'contradiction': 0},
                'verifier': 'nli_unavailable',
                'model': self.model_name,
                'error': self._load_error,
            }

        if not answer or not answer.strip() or not chunks:
            return {
                'supported_ratio': 0.0,
                'num_claims': 0,
                'sentence_verdicts': [],
                'label_distribution': {'entailment': 0, 'neutral': 0, 'contradiction': 0},
                'verifier': 'nli',
                'model': self.model_name,
            }

        claims = self._split_claims(answer)
        if not claims:
            return {
                'supported_ratio': 0.0,
                'num_claims': 0,
                'sentence_verdicts': [],
                'label_distribution': {'entailment': 0, 'neutral': 0, 'contradiction': 0},
                'verifier': 'nli',
                'model': self.model_name,
            }

        # Build a pair for every (chunk premise, claim hypothesis).
        # CrossEncoder.predict expects (premise, hypothesis) pairs.
        pairs: list[tuple[str, str]] = []
        for claim in claims:
            for chunk in chunks:
                pairs.append((chunk.content, claim))

        import numpy as np

        raw_scores = self._model.predict(pairs, convert_to_numpy=True)
        # Softmax per row to get probabilities.
        exp_scores = np.exp(raw_scores - raw_scores.max(axis=1, keepdims=True))
        probs = exp_scores / exp_scores.sum(axis=1, keepdims=True)

        # Find the column indices for each label from the model's id2label.
        label_to_col = {label: idx for idx, label in self._id2label.items()}
        ent_col = label_to_col.get('entailment', 1)
        con_col = label_to_col.get('contradiction', 0)
        neu_col = label_to_col.get('neutral', 2)

        num_chunks = len(chunks)
        verdicts: list[dict] = []
        label_dist = {'entailment': 0, 'neutral': 0, 'contradiction': 0}

        for i, claim in enumerate(claims):
            # Slice the rows for this claim — one row per chunk.
            claim_probs = probs[i * num_chunks : (i + 1) * num_chunks]
            ent_probs = claim_probs[:, ent_col]
            best_idx = int(ent_probs.argmax())
            best_row = claim_probs[best_idx]
            best_ent = float(best_row[ent_col])
            best_con = float(best_row[con_col])
            best_neu = float(best_row[neu_col])

            # Label wins by argmax on the three class probabilities.
            label_probs = {
                'entailment': best_ent,
                'neutral': best_neu,
                'contradiction': best_con,
            }
            label = max(label_probs, key=lambda k: label_probs[k])

            # Treat as supported only if entailment clears the threshold.
            supported = best_ent >= self.entailment_threshold and label == 'entailment'
            label_dist[label] += 1

            verdicts.append(
                {
                    'sentence': claim,
                    'label': label,
                    'entailment_score': round(best_ent, 4),
                    'neutral_score': round(best_neu, 4),
                    'contradiction_score': round(best_con, 4),
                    'best_chunk_idx': best_idx,
                    'supported': supported,
                }
            )

        supported_count = sum(1 for v in verdicts if v['supported'])
        ratio = round(supported_count / len(verdicts), 4) if verdicts else 0.0

        return {
            'supported_ratio': ratio,
            'num_claims': len(verdicts),
            'sentence_verdicts': verdicts,
            'label_distribution': label_dist,
            'verifier': 'nli',
            'model': self.model_name,
        }

    def verify_pair(
        self,
        claim: str,
        evidence: str,
        threshold: float | None = None,
    ) -> dict:
        """Score one (claim, evidence) pair and return per-class probabilities.

        Thin wrapper around a single cross-encoder forward pass. Returns
        the primitive shape `{"entailment": float, "neutral": float,
        "contradiction": float, "verified": bool}` — useful when the
        caller has already isolated a single claim and a single piece of
        supporting evidence (e.g. external test harnesses, shadow-mode
        diagnostics, spot-check tools).

        The richer `verify_grounding(answer, chunks)` method orchestrates
        many of these over the retrieved chunk set; this method is the
        underlying primitive and is safe to call directly.

        Raises `NotImplementedError` when the model cannot be loaded —
        chosen deliberately over silently returning fake scores so an
        external caller cannot mistake a "model missing" state for a
        real neutral verdict. The higher-level `verify_grounding` path
        still returns a sentinel dict in that case because the RAG
        orchestrator needs to degrade gracefully.
        """
        if not self._load_model():
            raise NotImplementedError(
                f'NLI verifier unavailable: {self._load_error}. '
                f'Install sentence-transformers and ensure the model can be '
                f'downloaded, or use the TF-IDF VerificationService instead.'
            )

        threshold = self.entailment_threshold if threshold is None else threshold

        import numpy as np

        raw = self._model.predict([(evidence, claim)], convert_to_numpy=True)
        # Shape is (1, 3). Softmax over the class axis.
        row = raw[0]
        exp = np.exp(row - row.max())
        probs = exp / exp.sum()

        label_to_col = {label: idx for idx, label in self._id2label.items()}
        ent = float(probs[label_to_col.get('entailment', 1)])
        neu = float(probs[label_to_col.get('neutral', 2)])
        con = float(probs[label_to_col.get('contradiction', 0)])
        return {
            'entailment': round(ent, 4),
            'neutral': round(neu, 4),
            'contradiction': round(con, 4),
            'verified': ent > threshold,
        }

    def _split_claims(self, text: str) -> list[str]:
        """Split answer text into claim-sized sentences.

        Same tokenisation as the TF-IDF verifier so results are directly
        comparable. Strips citation markers like `[1]` before splitting.
        """
        clean = re.sub(r'\[\d+\]', '', text)
        parts = re.split(r'(?<=[.!?])\s+', clean)
        return [s.strip() for s in parts if len(s.strip()) > 15]


__all__ = ['EntailmentLabel', 'NLIVerifier']

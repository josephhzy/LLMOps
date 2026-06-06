"""Policy service — request and response guardrails.

Pre-checks: prompt injection detection with unicode normalization, input validation.
Post-checks: grounding support threshold enforcement.
Includes PII masking hook and audit logging for all policy decisions.

WARNING — injection detector is NOT production-ready.
    The regex list in ``INJECTION_PATTERNS`` below is a placeholder. Against
    the 30-prompt hand-curated adversarial/benign set in ``scripts/eval_injection.py``
    it scores 0/15 recall on adversarial prompts (and 0/15 false positives on
    benign prompts). Do NOT rely on this module as a deployed guardrail. It
    exists as scaffolding for a future classifier-based detector; see
    ``docs/INJECTION_EVAL.md`` for the numbers and the planned replacement.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata

from app.core.audit import audit
from app.core.exceptions import PolicyViolationError
from app.core.logging import get_logger
from app.core.metrics import POLICY_ACTION
from app.models.api import QueryRequest
from app.models.enums import PolicyAction

logger = get_logger(__name__)

# Patterns that indicate prompt injection attempts
INJECTION_PATTERNS = [
    r'ignore\s+(all\s+)?previous\s+instructions',
    r'ignore\s+(all\s+)?above\s+instructions',
    r'disregard\s+(all\s+)?previous',
    r'forget\s+(all\s+)?previous',
    r'you\s+are\s+now\s+a',
    r'new\s+instructions?\s*:',
    r'system\s+prompt\s*:',
    r'<\s*/?system\s*>',
    r'act\s+as\s+(if\s+)?(you\s+are\s+)?a',
    r'pretend\s+(you\s+are|to\s+be)',
    # Additional patterns to reduce bypass surface
    r'discard\s+(your\s+)?(system\s+)?prompt',
    r'behave\s+as\s+if\s+(you\s+)?(have\s+)?no\s+(safety|rules|restrictions)',
    r'override\s+(all\s+)?(safety|security)',
    r'jailbreak',
    r'do\s+anything\s+now',
    r'developer\s+mode',
    r'ignore\s+(any|all)\s+(rules|constraints|guidelines)',
]

_compiled_patterns = [re.compile(p, re.IGNORECASE) for p in INJECTION_PATTERNS]


def _normalize_text(text: str) -> str:
    """Normalize unicode and whitespace to defeat obfuscation.

    - NFKC normalization collapses homoglyphs (Cyrillic i -> Latin i)
    - Strips zero-width characters
    - Collapses multiple spaces
    """
    # NFKC normalization handles homoglyphs and compatibility chars
    text = unicodedata.normalize('NFKC', text)
    # Strip zero-width characters
    text = re.sub(r'[\u200b\u200c\u200d\u2060\ufeff]', '', text)
    # Collapse multiple whitespace
    text = re.sub(r'\s+', ' ', text)
    return text


class PolicyService:
    """Request and response policy enforcement."""

    def precheck_request(self, request: QueryRequest) -> None:
        """Block injection-style requests before retrieval/generation.

        Applies unicode normalization before pattern matching to resist
        homoglyph and zero-width character bypass techniques.
        """
        normalized = _normalize_text(request.question)

        for pattern in _compiled_patterns:
            if pattern.search(normalized):
                logger.warning(
                    'policy_violation',
                    violation='injection_detected',
                    pattern=pattern.pattern,
                    question_preview=request.question[:100],
                )
                POLICY_ACTION.labels(action='BLOCK').inc()
                # Forensic target: first 16 hex chars of SHA-256 over the raw prompt.
                # We deliberately do NOT persist the raw prompt text to avoid
                # echoing PII or an attacker's payload into the audit trail.
                prompt_hash = hashlib.sha256(request.question.encode('utf-8', errors='replace')).hexdigest()[:16]
                audit.log_event(
                    'policy',
                    'system',
                    'block_injection',
                    target=prompt_hash,
                    outcome='denied',
                    details={
                        'prompt_length': len(request.question),
                        'category': pattern.pattern,
                    },
                )
                raise PolicyViolationError('Prompt injection detected. Request blocked by policy.')

        # PII masking hook — interface for future implementation
        self._pii_check_hook(request)

    def postcheck_response(self, supported_ratio: float) -> PolicyAction:
        """Final response decision based on grounding support strength.

        Thresholds:
        - >= 0.75: ALLOW (well-grounded)
        - >= 0.50: ALLOW_WITH_WARNING (partially grounded)
        - < 0.50: ABSTAIN (insufficient evidence)
        """
        if supported_ratio >= 0.75:
            action = PolicyAction.ALLOW
        elif supported_ratio >= 0.50:
            action = PolicyAction.ALLOW_WITH_WARNING
        else:
            action = PolicyAction.ABSTAIN

        POLICY_ACTION.labels(action=action.value).inc()
        logger.info('policy_postcheck', action=action.value, support_ratio=supported_ratio)
        return action

    def _pii_check_hook(self, request: QueryRequest) -> None:
        """Hook for PII detection and masking.

        Intended integration point: attach a PII detection model or regex engine
        to detect government ID numbers, phone numbers, email addresses, etc. and mask before retrieval.
        """
        # Not yet implemented; no PII masking applied
        pass

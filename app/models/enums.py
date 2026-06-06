from enum import StrEnum


class PolicyAction(StrEnum):
    """Response policy actions.

    ALLOW, ALLOW_WITH_WARNING, and ABSTAIN are the post-check outcomes
    returned by PolicyService.postcheck_response(). BLOCK is the pre-check
    outcome emitted by PolicyService.precheck_request() on prompt injection.
    REDACT and ESCALATE are reserved for future policy rules (e.g., PII
    detection, classification violations).
    """

    ALLOW = 'ALLOW'
    ALLOW_WITH_WARNING = 'ALLOW_WITH_WARNING'
    ABSTAIN = 'ABSTAIN'
    REDACT = 'REDACT'  # Reserved: PII detection
    ESCALATE = 'ESCALATE'  # Reserved: classification violation
    BLOCK = 'BLOCK'  # Active (pre-check): adversarial / injection content

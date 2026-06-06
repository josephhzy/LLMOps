class PolicyViolationError(Exception):
    """Raised when request or output violates policy."""


class VerificationError(Exception):
    """Raised when output support checks fail."""

"""Verification package — grounding / entailment verifiers.

Contains the TF-IDF heuristic that is the default in-use verifier (imported
from `app.services.verification_service`) and the NLI verifier
(`nli_verifier.py`), which is fully implemented but not enabled on the default
request path — it runs in shadow mode behind the `NLI_SHADOW_ENABLED` flag.
"""

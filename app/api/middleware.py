"""Error handling, metrics, and authentication middleware.

Catches known exception types and returns structured JSON errors.
Records request counts and latency for Prometheus.
Authenticates requests via Bearer token with role mapping from API_KEYS env var.
"""

from __future__ import annotations

import json
import os
import time

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.exceptions import PolicyViolationError, VerificationError
from app.core.logging import get_logger
from app.core.metrics import REQUEST_COUNT, REQUEST_LATENCY

logger = get_logger(__name__)

# Load API key -> role mapping from API_KEYS env var (JSON string).
# Format: {"key1": "admin", "key2": "viewer"}
# If not set, falls back to empty dict (all requests default to "public").
_API_KEYS_RAW = os.environ.get('API_KEYS', '{}')
try:
    _API_KEY_ROLES: dict[str, str] = json.loads(_API_KEYS_RAW)
except (json.JSONDecodeError, TypeError):
    _API_KEY_ROLES = {}


class AuthMiddleware(BaseHTTPMiddleware):
    """Authenticate requests via Bearer token and store role in request.state.

    - Checks for Authorization: Bearer <key> header.
    - Maps API keys to roles via API_KEYS env var (JSON dict).
    - Only sets request.state.role when a valid Bearer token resolves a role.
      Otherwise request.state.role is left unset and the request continues
      unchanged — this middleware performs NO authentication enforcement and
      will NOT reject unauthenticated requests. Routes that require auth must
      declare an explicit Depends(get_current_user) or Depends(require_admin)
      guard. NOTE: /metrics, /v1/admin/versions, /v1/admin/config, and the
      registry read routes (GET /v1/admin/registry*) currently have no such
      guard and are therefore publicly accessible.
    """

    async def dispatch(self, request: Request, call_next):
        auth_header = request.headers.get('Authorization', '')

        if auth_header.startswith('Bearer '):
            token = auth_header[len('Bearer ') :]
            mapped_role = _API_KEY_ROLES.get(token)
            if mapped_role:
                request.state.role = mapped_role
                logger.debug('auth_resolved', role=mapped_role)
            else:
                logger.debug('auth_unknown_token', token_prefix=token[:8] if token else '')

        response = await call_next(request)
        return response


class ErrorHandlerMiddleware(BaseHTTPMiddleware):
    """Catches exceptions and returns structured JSON error responses."""

    async def dispatch(self, request: Request, call_next):
        start = time.perf_counter()
        try:
            response = await call_next(request)
            REQUEST_COUNT.labels(
                endpoint=request.url.path,
                method=request.method,
                status=response.status_code,
            ).inc()
            return response

        except PolicyViolationError as e:
            REQUEST_COUNT.labels(endpoint=request.url.path, method=request.method, status=403).inc()
            return JSONResponse(
                status_code=403,
                content={'error': 'policy_violation', 'detail': str(e)},
            )

        except VerificationError as e:
            REQUEST_COUNT.labels(endpoint=request.url.path, method=request.method, status=422).inc()
            return JSONResponse(
                status_code=422,
                content={'error': 'verification_failed', 'detail': str(e)},
            )

        except Exception as e:
            logger.error('Unhandled error', path=request.url.path, error=str(e), exc_info=True)
            REQUEST_COUNT.labels(endpoint=request.url.path, method=request.method, status=500).inc()
            return JSONResponse(
                status_code=500,
                content={'error': 'internal_error', 'detail': 'An internal error occurred.'},
            )

        finally:
            duration = time.perf_counter() - start
            REQUEST_LATENCY.labels(endpoint=request.url.path).observe(duration)

"""Authentication and authorization.

API key-based auth with role mapping. In production, replace with
JWT validation or integration with an identity provider.

Dev mode: requests without an API key default to viewer role.
Admin access requires a valid API key.
"""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import Depends, HTTPException, Security
from fastapi.security import APIKeyHeader

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_api_key_header = APIKeyHeader(name='X-API-Key', auto_error=False)

# In production: load from secrets manager or database.
# For demo: configurable via environment or hardcoded dev keys.
_API_KEY_STORE: dict[str, dict] = {
    'dev-viewer-key': {'user_id': 'dev-viewer', 'role': 'viewer'},
    'dev-admin-key': {'user_id': 'dev-admin', 'role': 'admin'},
}


@dataclass
class AuthenticatedUser:
    """Validated identity from the auth layer. Never trust client-supplied roles."""

    user_id: str
    role: str


async def get_current_user(api_key: str | None = Security(_api_key_header)) -> AuthenticatedUser:
    """Resolve API key to an authenticated user.

    - Valid key: returns the mapped user with their authorized role.
    - No key (dev mode): returns anonymous viewer.
    - Invalid key: returns 401.
    """
    if api_key is None:
        # Dev mode: allow anonymous access as viewer
        if settings.env == 'dev':
            return AuthenticatedUser(user_id='anonymous', role='viewer')
        raise HTTPException(status_code=401, detail='API key required')

    user_data = _API_KEY_STORE.get(api_key)
    if user_data is None:
        logger.warning('Invalid API key attempted')
        raise HTTPException(status_code=401, detail='Invalid API key')

    return AuthenticatedUser(user_id=user_data['user_id'], role=user_data['role'])


async def require_admin(user: AuthenticatedUser = Depends(get_current_user)) -> AuthenticatedUser:
    """Authorize admin-only operations: resolve the caller, then enforce the admin role.

    Use as a route dependency for mutating governance endpoints (register/promote/revoke).
    """
    if user.role != 'admin':
        raise HTTPException(status_code=403, detail='Admin role required')
    return user

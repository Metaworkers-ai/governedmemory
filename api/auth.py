"""
Per-tenant API key auth for the self-hosted REST server (E7).

Self-hosted doesn't mean unauthenticated: every request must present a
Bearer token that maps to exactly one tenant_id, and that resolved
tenant_id -- never one a client sends in a request body -- is what every
route uses to call into MemoryStore. This is what stops a caller holding
tenant A's key from reading or writing tenant B's memories by simply
putting a different tenant_id in the request body (there isn't one to
put -- see api/schemas.py).

Configuration: GOVERNEDMEMORY_API_KEYS="tenant_id:key,tenant_id:key,...".
No database table, no admin UI -- matches this project's "self-host, zero
extra infra" stance.
"""

from __future__ import annotations

import os

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

_bearer_scheme = HTTPBearer(auto_error=False)


def _load_key_map() -> dict[str, str]:
    """key -> tenant_id, parsed fresh from the env var on every call (same
    "read env at call time, not import time" pattern core/detection/scanner.py
    uses for DETECTION_BACKEND) so tests can change keys without a reload."""
    raw = os.environ.get("GOVERNEDMEMORY_API_KEYS", "")
    key_map: dict[str, str] = {}
    for pair in raw.split(","):
        pair = pair.strip()
        if not pair:
            continue
        tenant_id, _, key = pair.partition(":")
        if tenant_id and key:
            key_map[key] = tenant_id
    return key_map


def require_tenant(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> str:
    """FastAPI dependency: resolves the caller's tenant_id from its API key.
    Every route depends on this instead of trusting a client-supplied tenant_id."""
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="missing Authorization: Bearer <api-key> header",
        )
    tenant_id = _load_key_map().get(credentials.credentials)
    if tenant_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid API key")
    return tenant_id

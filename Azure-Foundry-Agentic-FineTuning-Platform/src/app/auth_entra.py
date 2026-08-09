"""Validates Entra ID bearer tokens for the public hosted deployment.

Only active when `ENTRA_TENANT_ID` / `ENTRA_CLIENT_ID` are set (the Container
App build only — see hosting.tf) — local/mock dev never sets these, matching
the frontend's `isEntraEnabled` gate, so `require_entra_auth` is a no-op
there and nothing changes about local development.

Why this exists instead of Container Apps' built-in Easy Auth: Easy Auth
authenticates the browser's CORS preflight (`OPTIONS`) request too, and a
preflight structurally never carries credentials — so Easy Auth always 401s
it, breaking every cross-origin call from the SPA before it starts.
Confirmed live (`curl -X OPTIONS ... -H "Origin: ..."` returned 401 with
Easy Auth enabled) and matches a known, unresolved Container Apps platform
limitation (microsoft/azure-container-apps#359). Validating the token
ourselves, behind our own `CORSMiddleware` (which already answers OPTIONS
correctly, since Starlette handles preflight before any route dependency
runs), is the documented workaround for this exact SPA + separate-origin-API
shape.
"""

from __future__ import annotations

import jwt
from fastapi import HTTPException, Request, status
from jwt import PyJWKClient

from app.config import get_settings

_jwks_clients: dict[str, PyJWKClient] = {}


def _jwks_client(tenant_id: str) -> PyJWKClient:
    # Cached per tenant (there's only ever one in practice) — PyJWKClient
    # itself caches the fetched keys internally, so this just avoids
    # rebuilding the client object on every request.
    if tenant_id not in _jwks_clients:
        _jwks_clients[tenant_id] = PyJWKClient(
            f"https://login.microsoftonline.com/{tenant_id}/discovery/v2.0/keys"
        )
    return _jwks_clients[tenant_id]


async def require_entra_auth(request: Request) -> None:
    """FastAPI dependency — raises 401 unless the request carries a valid
    Entra ID access token for this app's exposed API scope."""
    settings = get_settings()
    if not settings.entra_tenant_id or not settings.entra_client_id:
        return

    auth_header = request.headers.get("authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="missing bearer token")
    token = auth_header.removeprefix("Bearer ").strip()

    try:
        signing_key = _jwks_client(settings.entra_tenant_id).get_signing_key_from_jwt(token)
        jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            # For this app's "SPA calling its own exposed API" shape,
            # Entra stamps `aud` as the resource app's client ID (a GUID),
            # not its App ID URI — confirmed by decoding a real issued
            # token live, not assumed from docs (the identifier-URI
            # assumption was wrong and cost a round of debugging).
            audience=settings.entra_client_id,
            issuer=f"https://login.microsoftonline.com/{settings.entra_tenant_id}/v2.0",
        )
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=f"invalid token: {exc}"
        ) from exc

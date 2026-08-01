"""A deliberately minimal demo sign-in gate.

**This is not production authentication and does not pretend to be.** There is
one hard-coded account, no user store, no password hashing at rest, no
registration, no reset flow, and no SSO. It exists for two reasons:

1. It gives the showcase the corporate look-and-feel a stakeholder expects.
2. It is a real gate, not a client-side facade. The ALB in front of this app is
   public and every demo endpoint spends money on model calls, so leaving them
   open to anyone who stumbles onto the DNS name would be careless. Session
   validation happens server-side, and the demo routers are mounted behind
   `require_session`.

The session cookie is an HMAC over the username and an issue timestamp, signed
with `SHOWCASE_SESSION_SECRET`. When that variable is unset a random secret is
generated per process, so restarting the task invalidates every session — the
safe default for a deployment where no one has deliberately chosen a secret.

Swapping this for real auth means replacing `authenticate()` and `require_session`
with an OIDC flow; nothing else in the app knows how sessions are established.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets
import time

from fastapi import Cookie, HTTPException

SESSION_COOKIE = "showcase_session"
SESSION_TTL_SECONDS = 12 * 60 * 60

DEMO_USERNAME = os.environ.get("SHOWCASE_DEMO_USER", "demo@contoso.com")
DEMO_PASSWORD = os.environ.get("SHOWCASE_DEMO_PASSWORD", "contoso")

_SECRET = os.environ.get("SHOWCASE_SESSION_SECRET") or secrets.token_hex(32)


def _sign(payload: str) -> str:
    digest = hmac.new(_SECRET.encode(), payload.encode(), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest).decode().rstrip("=")


def authenticate(username: str, password: str) -> bool:
    """Constant-time comparison on both fields, so neither leaks via timing."""
    return secrets.compare_digest(username.strip().lower(), DEMO_USERNAME.lower()) and (
        secrets.compare_digest(password, DEMO_PASSWORD)
    )


def issue_session(username: str) -> str:
    payload = f"{username}|{int(time.time())}"
    return f"{base64.urlsafe_b64encode(payload.encode()).decode().rstrip('=')}.{_sign(payload)}"


def read_session(token: str | None) -> str | None:
    """Return the signed-in username, or None if the token is absent/invalid/expired."""
    if not token or "." not in token:
        return None
    encoded, signature = token.rsplit(".", 1)
    try:
        payload = base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)).decode()
    except (ValueError, UnicodeDecodeError):
        return None
    if not hmac.compare_digest(_sign(payload), signature):
        return None
    username, _, issued_at = payload.rpartition("|")
    try:
        if time.time() - int(issued_at) > SESSION_TTL_SECONDS:
            return None
    except ValueError:
        return None
    return username


async def require_session(showcase_session: str | None = Cookie(default=None)) -> str:
    """FastAPI dependency guarding every demo endpoint."""
    username = read_session(showcase_session)
    if username is None:
        raise HTTPException(status_code=401, detail="Sign in to use the demos")
    return username

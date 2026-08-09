"""Static demo authentication.

This is a **demo gate, not authentication.** Credentials are a fixed pair from
config, the token is an opaque constant, and nothing is verified server-side on
subsequent requests. It exists so the UI has a login screen, and is deliberately
transparent about that rather than implying real security.

Do not copy this into anything that needs actual auth.
"""

from __future__ import annotations

import hmac
from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.config import get_settings

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=128)


class LoginResponse(BaseModel):
    authenticated: bool
    username: str
    token: str
    notice: str


@router.post("/login", response_model=LoginResponse)
async def login(payload: LoginRequest) -> LoginResponse:
    settings = get_settings()

    # compare_digest on both fields to avoid a trivial timing signal, even though
    # the credentials are public by design.
    ok = hmac.compare_digest(payload.username, settings.demo_username) and hmac.compare_digest(
        payload.password, settings.demo_password
    )
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid demo credentials. Use demo / demo123.",
        )

    return LoginResponse(
        authenticated=True,
        username=payload.username,
        token="demo-session-token",
        notice="Static demo gate — not real authentication.",
    )


@router.get("/config")
async def auth_config() -> dict[str, Any]:
    """Tell the UI this is a demo gate so it can label the screen honestly."""
    return {
        "mode": "static-demo",
        "hint": "demo / demo123",
        "is_real_authentication": False,
    }

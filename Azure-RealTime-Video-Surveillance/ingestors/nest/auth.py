from __future__ import annotations

import logging
import time

import requests

logger = logging.getLogger("nest_ingestor.auth")

TOKEN_URL = "https://www.googleapis.com/oauth2/v4/token"
_EXPIRY_SAFETY_MARGIN_SECONDS = 60


class GoogleTokenManager:
    """Refreshes and caches a Google OAuth access token from a long-lived
    refresh_token. Access tokens expire hourly (3600s); this proactively
    refreshes a minute before expiry rather than reacting to a 401.
    """

    def __init__(self, client_id: str, client_secret: str, refresh_token: str) -> None:
        self._client_id = client_id
        self._client_secret = client_secret
        self._refresh_token = refresh_token
        self._access_token: str | None = None
        self._expires_at: float = 0.0

    def get_access_token(self) -> str:
        if self._access_token is None or time.monotonic() >= self._expires_at:
            self._refresh()
        return self._access_token  # type: ignore[return-value]

    def _refresh(self) -> None:
        logger.info("Refreshing Google OAuth access token")
        response = requests.post(
            TOKEN_URL,
            data={
                "client_id": self._client_id,
                "client_secret": self._client_secret,
                "refresh_token": self._refresh_token,
                "grant_type": "refresh_token",
            },
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()
        self._access_token = payload["access_token"]
        expires_in = payload.get("expires_in", 3600)
        self._expires_at = time.monotonic() + expires_in - _EXPIRY_SAFETY_MARGIN_SECONDS

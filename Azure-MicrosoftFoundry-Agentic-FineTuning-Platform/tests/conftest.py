"""Shared pytest fixtures. Forces mock mode for anything not marked `live`."""

from __future__ import annotations

import os

os.environ.setdefault("DEMO_MODE", "mock")

import pytest

from app.config import get_settings


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    """`get_settings()` is `@lru_cache`d; clear it so env overrides in a test
    (e.g. `monkeypatch.setenv`) actually take effect on the next call."""
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()

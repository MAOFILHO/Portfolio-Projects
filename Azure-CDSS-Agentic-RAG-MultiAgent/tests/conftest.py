"""Shared pytest fixtures."""

from __future__ import annotations

import json
from pathlib import Path

import pytest


@pytest.fixture
def tmp_state_file(tmp_path: Path) -> Path:
    return tmp_path / "deployment_state.json"


@pytest.fixture
def sample_state_data() -> dict:
    return {
        "steps": {
            "s00_preflight": {
                "name": "s00_preflight",
                "status": "completed",
                "started_at": "2025-01-01T00:00:00+00:00",
                "completed_at": "2025-01-01T00:00:05+00:00",
                "error": None,
                "outputs": {},
            }
        },
        "resource_group": "cdss-test-rg",
        "location": "westus2",
        "subscription_id": "test-sub-id",
        "deployed_resources": {"app_name": "cdss-test-api"},
        "created_at": "2025-01-01T00:00:00+00:00",
        "updated_at": "2025-01-01T00:00:05+00:00",
    }


@pytest.fixture
def populated_state_file(tmp_state_file: Path, sample_state_data: dict) -> Path:
    tmp_state_file.write_text(json.dumps(sample_state_data, indent=2))
    return tmp_state_file

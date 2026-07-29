from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT / "shared"))
sys.path.insert(0, str(REPO_ROOT / "backend"))
sys.path.insert(0, str(REPO_ROOT / "ingestors" / "nest"))
sys.path.insert(0, str(REPO_ROOT / "function"))

import pytest  # noqa: E402


@pytest.fixture
def tmp_state_file(tmp_path: Path) -> Path:
    return tmp_path / "deployment_state.json"

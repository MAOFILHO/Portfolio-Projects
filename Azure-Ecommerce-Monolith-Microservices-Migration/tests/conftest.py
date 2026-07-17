"""Shared pytest fixtures/path setup for the repo-root test venv.

Only infra/, scripts/, and bff/ are added to sys.path here. monolith/app and
each microservice's application/ are each their OWN top-level package (and
every service has its own top-level config.py) — collision-free when each
runs in its own process/venv, but NOT collision-free if multiple were on
sys.path in one pytest session (they'd all fight over the same module name).
Per-service unit tests instead live inside each service directory and run
with that service's own venv — see monolith/tests/, microservices/*/tests/.
"""
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]

for path in [REPO_ROOT, REPO_ROOT / "infra", REPO_ROOT / "scripts", REPO_ROOT / "bff"]:
    sys.path.insert(0, str(path))


@pytest.fixture
def repo_root() -> Path:
    return REPO_ROOT

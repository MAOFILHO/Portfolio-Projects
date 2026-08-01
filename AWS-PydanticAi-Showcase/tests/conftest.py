import os

# Agent construction resolves the configured provider eagerly, so a dummy key
# must be in place *before* `app.agents` (and anything that imports it) gets
# imported below — a fixture would run too late. No real request is ever
# made: `block_real_model_requests` below enforces that, and every test
# overrides the model with TestModel/FunctionModel.
os.environ.setdefault("OPENAI_API_KEY", "sk-test-mock-key-for-offline-tests")

import pytest
from pydantic_ai import models


@pytest.fixture(autouse=True, scope="session")
def block_real_model_requests():
    """Fail loudly if a test ever tries to reach a real model provider."""
    models.ALLOW_MODEL_REQUESTS = False
    yield

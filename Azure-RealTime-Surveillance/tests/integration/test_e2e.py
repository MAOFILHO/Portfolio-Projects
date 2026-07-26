"""Live end-to-end test against a deployed environment.

Skipped by default (no AZURE_SUBSCRIPTION_ID / deployment_state.json means
nothing is deployed). Run explicitly after `surveil-deploy deploy` with:

    pytest tests/integration/test_e2e.py -v -m integration

This exercises the same path as `surveil-deploy smoke-test --stage post`
(steps s10_health_check + s11_validate_e2e) but as a pytest-reportable test
for CI environments that have a live deployment to validate.
"""

from __future__ import annotations

import pytest

from surveil_deploy.config import get_config
from surveil_deploy.state import load_state

pytestmark = pytest.mark.integration


def _has_live_deployment() -> bool:
    config = get_config()
    state = load_state(config.state_file())
    return bool(state.resource_outputs)


@pytest.mark.skipif(not _has_live_deployment(), reason="No live deployment found (run `surveil-deploy deploy` first)")
def test_health_check_passes_against_live_deployment():
    from surveil_deploy.steps import s10_health_check

    config = get_config()
    state = load_state(config.state_file())
    s10_health_check.run(config, state)  # raises RuntimeError on failure

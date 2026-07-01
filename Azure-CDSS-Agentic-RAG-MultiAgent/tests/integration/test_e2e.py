"""End-to-end integration tests (require live Azure credentials).

Run with: pytest tests/integration/ -v -m integration
"""

from __future__ import annotations

import pytest


@pytest.mark.integration
def test_placeholder() -> None:
    """Placeholder for live Azure e2e tests.

    Full e2e tests would:
    1. Run cdss-deploy deploy (or individual steps)
    2. Verify health check passes
    3. Verify patient API returns data
    4. Run cdss-deploy teardown
    """
    pytest.skip("Requires live Azure credentials and costs money")

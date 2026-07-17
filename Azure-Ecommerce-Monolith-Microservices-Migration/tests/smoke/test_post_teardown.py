"""Post-teardown smoke test: confirms every Azure resource from provision.py
is actually gone after `make teardown`. This mirrors infra/verify_teardown.py
(which polls with backoff since deletion is async) as a pytest-runnable
check — use verify_teardown.py directly for the real wait loop; this test is
the fast one-shot version for CI-style runs where teardown+verify already
completed."""
import json
import subprocess

import pytest


def test_no_leftover_resource_group(repo_root):
    state_file = repo_root / "infra" / ".state.json"
    if not state_file.exists():
        pytest.skip("infra/.state.json not present — nothing was provisioned, or teardown+verify already completed")

    state = json.loads(state_file.read_text())
    resource_group = state["resource_group"]

    result = subprocess.run(["az", "group", "show", "--name", resource_group, "--output", "json"], capture_output=True, text=True)
    assert result.returncode != 0, (
        f"Resource group '{resource_group}' still exists. Deletion is asynchronous — "
        f"run `python infra/verify_teardown.py` to wait for it, or re-run `make teardown`."
    )

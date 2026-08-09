"""Post-teardown smoke test — the release blocker.

Asserts ZERO resource groups tagged `managed_by = foundry-agentic-platform`
survive, at ANY auto-increment suffix, after `make teardown`. This is the
concrete mitigation for the naming-collision risk documented in PLAN.md and
`infra/terraform/scripts/next_suffix.py`'s docstring: `terraform destroy`
alone only removes the suffix currently in state, so if `.suffix.lock` was
ever lost, this is what actually catches an orphaned `-v1` while state has
moved on to `-v2`.

Marked `post_teardown` (a release blocker per the project's standing rules)
and skipped unless RUN_LIVE_SMOKE=1, since it queries real Azure.
"""

from __future__ import annotations

import json
import os
import subprocess

import pytest

_LIVE = os.environ.get("RUN_LIVE_SMOKE") == "1"
_TAG = "foundry-agentic-platform"

pytestmark = [
    pytest.mark.smoke_post_teardown,
    pytest.mark.post_teardown,
    pytest.mark.skipif(not _LIVE, reason="set RUN_LIVE_SMOKE=1"),
]


def _tagged_resource_groups() -> list[str]:
    proc = subprocess.run(
        [
            "az",
            "group",
            "list",
            "--query",
            f"[?tags.managed_by=='{_TAG}'].name",
            "-o",
            "json",
        ],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout or "[]")


def test_no_tagged_resource_groups_survive_at_any_suffix():
    survivors = _tagged_resource_groups()
    assert survivors == [], (
        f"{len(survivors)} orphaned resource group(s) still tagged "
        f"managed_by={_TAG}: {survivors} — teardown is incomplete. Run "
        f"`python infra/terraform/scripts/sweep_orphans.py --tag {_TAG}`."
    )

"""Unit tests for infra/terraform/scripts/next_suffix.py — the auto-increment
naming logic (see PLAN.md's "Naming on collision" decision and residual-risk
note). Runs the script as a subprocess exactly as Terraform's `external`
provider does: query JSON on stdin, result JSON on stdout.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "infra" / "terraform" / "scripts" / "next_suffix.py"


def _run(query: dict) -> dict:
    proc = subprocess.run(
        [sys.executable, str(SCRIPT)],
        input=json.dumps(query),
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


def test_fast_path_no_lock_defaults_to_v1(tmp_path):
    lock = tmp_path / ".suffix.lock"
    result = _run(
        {
            "project_name": "foundry-travel",
            "managed_by_tag": "foundry-agentic-platform",
            "enable_probe": "false",
            "lock_path": str(lock),
        }
    )
    assert result["suffix"] == "v1"
    assert result["probed"] == "false"
    assert lock.read_text().strip() == "v1"


def test_fast_path_reuses_existing_lock(tmp_path):
    lock = tmp_path / ".suffix.lock"
    lock.write_text("v7\n")
    result = _run(
        {
            "project_name": "foundry-travel",
            "managed_by_tag": "foundry-agentic-platform",
            "enable_probe": "false",
            "lock_path": str(lock),
        }
    )
    # Convergence: re-running must not drift the suffix without a real probe.
    assert result["suffix"] == "v7"


def test_probe_path_with_no_az_cli_treats_everything_as_free(tmp_path, monkeypatch):
    # shutil.which("az") returns None in a sandbox with no Azure CLI on PATH —
    # the script must still terminate and pick v1 rather than hang or crash.
    monkeypatch.setenv("PATH", str(tmp_path))  # empty PATH -> no `az` found
    lock = tmp_path / ".suffix.lock"
    result = _run(
        {
            "project_name": "foundry-travel",
            "managed_by_tag": "foundry-agentic-platform",
            "enable_probe": "true",
            "lock_path": str(lock),
        }
    )
    assert result["suffix"] == "v1"
    assert result["probed"] == "true"


def test_output_is_valid_external_provider_shape(tmp_path):
    lock = tmp_path / ".suffix.lock"
    result = _run(
        {
            "project_name": "foundry-travel",
            "managed_by_tag": "foundry-agentic-platform",
            "enable_probe": "false",
            "lock_path": str(lock),
        }
    )
    # Terraform's `external` provider requires a flat string->string map.
    assert all(isinstance(k, str) and isinstance(v, str) for k, v in result.items())

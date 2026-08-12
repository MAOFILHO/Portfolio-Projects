#!/usr/bin/env python3
"""Terraform `external` data source: picks a numeric name suffix.

⚠️  This is the auto-increment-on-collision pattern the guide-to-python-project
skill normally forbids ("never write rename-on-collision logic — it orphans
billable resources"). It exists here because the user explicitly chose it over
the safer alternative (see PLAN.md — "Naming on collision" decision row). Every
resource in this design bills $0/hour, which is what makes the residual risk of
an orphaned resource group acceptable rather than merely tolerable.

Protocol (Terraform `external` provider):
  stdin  -> JSON object of string -> string  ("query")
  stdout -> JSON object of string -> string  ("result")
  any non-zero exit / stderr output = Terraform treats it as a failed apply.

Query keys:
  project_name     e.g. "foundry-travel"
  managed_by_tag   e.g. "foundry-agentic-platform"
  enable_probe     "true" | "false" — if "false", skips the Azure CLI probe
                    entirely (used for `terraform validate`/`plan` in CI, where
                    there may be no `az login`) and always returns the locked
                    or default suffix.
  lock_path        path to `.suffix.lock`, relative to the terraform root.

Convergence rule: if a resource group already exists at the candidate name AND
carries `managed_by = <managed_by_tag>`, we return that SAME suffix — so
re-running `apply` is idempotent and never drifts. Only a name collision with
something NOT ours advances the counter.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path


def _az_group_tags(name: str) -> dict[str, str] | None:
    """Return the resource group's tags, or None if it does not exist."""
    az = shutil.which("az")
    if az is None:
        # No Azure CLI available — treat as "cannot verify, assume free" so
        # `plan` still works in a sandbox with no CLI installed.
        return None
    try:
        proc = subprocess.run(
            [az, "group", "show", "--name", name, "--query", "tags", "-o", "json"],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (subprocess.TimeoutExpired, OSError):
        return None
    if proc.returncode != 0:
        return None  # group does not exist (or no access) -> treat as free
    try:
        tags = json.loads(proc.stdout or "{}")
        return tags if isinstance(tags, dict) else {}
    except json.JSONDecodeError:
        return {}


def main() -> None:
    query = json.load(sys.stdin)
    project_name = query["project_name"]
    managed_by_tag = query["managed_by_tag"]
    enable_probe = query.get("enable_probe", "false").lower() == "true"
    lock_path = Path(query["lock_path"])

    locked_suffix = lock_path.read_text().strip() if lock_path.exists() else None

    if not enable_probe:
        # Fast, deterministic path for CI/validate — no Azure calls, no drift.
        suffix = locked_suffix or "v1"
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        lock_path.write_text(suffix + "\n")
        print(json.dumps({"suffix": suffix, "probed": "false"}))
        return

    # Live probe path.
    if locked_suffix:
        rg_name = f"rg-{project_name}-{locked_suffix}"
        tags = _az_group_tags(rg_name)
        if tags is None or tags.get("managed_by") == managed_by_tag:
            # Free, or already ours -> converge on the locked value.
            print(json.dumps({"suffix": locked_suffix, "probed": "true"}))
            return
        # Locked suffix is now held by something else — fall through and
        # start probing forward from v1 for the next free/owned slot.

    n = 1
    while True:
        candidate = f"v{n}"
        rg_name = f"rg-{project_name}-{candidate}"
        tags = _az_group_tags(rg_name)
        if tags is None or tags.get("managed_by") == managed_by_tag:
            lock_path.parent.mkdir(parents=True, exist_ok=True)
            lock_path.write_text(candidate + "\n")
            print(json.dumps({"suffix": candidate, "probed": "true"}))
            return
        n += 1
        if n > 999:  # sanity bound — never spin forever
            print("next_suffix.py: exhausted 999 suffix candidates", file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":
    main()

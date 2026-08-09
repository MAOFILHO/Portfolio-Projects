#!/usr/bin/env python3
"""Find and delete every resource group tagged `managed_by = <tag>`, at ANY
name suffix — not just the one Terraform currently has in state.

This is the primary mitigation for the auto-increment naming risk documented
in PLAN.md and `next_suffix.py`: if `.suffix.lock` is ever lost and a re-apply
mints `-v2` while `-v1` still exists, plain `terraform destroy` only tears down
the suffix in state and would orphan `-v1` forever. `make teardown` runs this
sweep both before AND after `terraform destroy` so nothing tagged with this
project survives, regardless of which suffix it landed on.

Usage:
    python sweep_orphans.py --tag foundry-agentic-platform [--dry-run]

Requires `az login` to already be done; uses the Azure CLI rather than the SDK
to keep this script dependency-free (it must run even if the venv is broken).
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys


def _az(*args: str) -> str:
    az = shutil.which("az")
    if az is None:
        print("sweep_orphans.py: `az` CLI not found on PATH", file=sys.stderr)
        sys.exit(1)
    proc = subprocess.run([az, *args], capture_output=True, text=True, timeout=120)
    if proc.returncode != 0:
        print(proc.stderr, file=sys.stderr)
        sys.exit(proc.returncode)
    return proc.stdout


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tag", required=True, help="managed_by tag value to sweep")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    raw = _az(
        "group", "list",
        "--query", f"[?tags.managed_by=='{args.tag}'].name",
        "-o", "json",
    )
    groups: list[str] = json.loads(raw or "[]")

    if not groups:
        print(f"sweep_orphans: no resource groups tagged managed_by={args.tag}")
        return 0

    print(f"sweep_orphans: found {len(groups)} tagged group(s): {', '.join(groups)}")

    for name in groups:
        if args.dry_run:
            print(f"  [dry-run] would delete {name}")
            continue
        print(f"  deleting {name} (async, --no-wait)...")
        _az("group", "delete", "--name", name, "--yes", "--no-wait")

    if not args.dry_run:
        print(
            "sweep_orphans: deletions submitted (async). Re-run with no "
            "--dry-run later, or `az group list`, to confirm they finished."
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())

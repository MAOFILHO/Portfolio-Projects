#!/usr/bin/env python3
"""make teardown — deletes every Azure resource provisioned by provision.py.

Reads infra/.state.json for the exact names that were actually used
(accounting for any auto-increment that happened on provision). Deleting the
whole resource group removes the Container Apps Environment, Container
Apps, ACR, MySQL Flexible Server, and Static Web App in one shot; the budget
alert (subscription-scoped) is deleted separately since it lives outside the
resource group.
"""
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
STATE_FILE = REPO_ROOT / "infra" / ".state.json"


def main() -> int:
    if not STATE_FILE.exists():
        print("No infra/.state.json found — nothing to tear down (or provision.py was never run).")
        return 0

    state = json.loads(STATE_FILE.read_text())
    resource_group = state["resource_group"]

    print(f"=== Deleting resource group '{resource_group}' (this removes every resource inside it) ===")
    result = subprocess.run(
        ["az", "group", "delete", "--name", resource_group, "--yes", "--no-wait", "--output", "json"],
    )
    if result.returncode != 0:
        print("Resource group deletion failed to start — check `az account show` and permissions.")
        return 1

    print("Deletion started asynchronously. This can take several minutes for MySQL Flexible Server.")
    print("Run `python infra/verify_teardown.py` (or `make verify`) to confirm everything is gone.")

    budget_name = f"{resource_group}-budget"
    print(f"\n=== Deleting budget alert '{budget_name}' ===")
    subprocess.run(["az", "consumption", "budget", "delete", "--budget-name", budget_name, "--output", "json"])

    # Keep .state.json until verify_teardown.py confirms deletion actually
    # completed (resource group deletion is async and can take minutes) —
    # deleting it now would leave nothing for verify/smoke tests to check
    # against. verify_teardown.py removes it once every resource is gone.
    print(f"\n{STATE_FILE} kept until `python infra/verify_teardown.py` confirms deletion is complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

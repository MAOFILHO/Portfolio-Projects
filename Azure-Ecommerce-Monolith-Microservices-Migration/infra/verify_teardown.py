#!/usr/bin/env python3
"""make verify — confirms every Azure resource from provision.py is actually
gone after teardown.py. Azure resource group deletion is asynchronous, so
this polls with backoff rather than checking once and declaring success.
Only removes infra/.state.json once everything is confirmed deleted.
"""
import json
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
STATE_FILE = REPO_ROOT / "infra" / ".state.json"

POLL_INTERVAL_SECONDS = 20
MAX_WAIT_SECONDS = 480  # 8 minutes — resource group deletion with MySQL Flexible Server can be slow


def resource_group_exists(name: str) -> bool:
    result = subprocess.run(["az", "group", "show", "--name", name, "--output", "json"], capture_output=True, text=True)
    return result.returncode == 0


def main() -> int:
    if not STATE_FILE.exists():
        print("No infra/.state.json found — nothing was provisioned, or teardown already completed. PASS.")
        return 0

    state = json.loads(STATE_FILE.read_text())
    resource_group = state["resource_group"]

    print(f"Waiting for resource group '{resource_group}' to be fully deleted…")
    deadline = time.monotonic() + MAX_WAIT_SECONDS
    while time.monotonic() < deadline:
        if not resource_group_exists(resource_group):
            print(f"PASS: resource group '{resource_group}' no longer exists.")
            print("This confirms ACR, Container Apps Environment + every Container App (monolith, bff, "
                  "and any of user-/product-/order-service created by a live migration), MySQL "
                  "Flexible Server, and the Static Web App were all deleted with it.")
            STATE_FILE.unlink()
            print(f"Removed {STATE_FILE}.")
            return 0
        print(f"  still deleting… (checking again in {POLL_INTERVAL_SECONDS}s)")
        time.sleep(POLL_INTERVAL_SECONDS)

    print(f"FAIL: resource group '{resource_group}' still exists after {MAX_WAIT_SECONDS}s. "
          f"Check the Azure Portal or run `az group show --name {resource_group}` — "
          f"deletion may have failed or still be in progress for a slow resource like MySQL.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

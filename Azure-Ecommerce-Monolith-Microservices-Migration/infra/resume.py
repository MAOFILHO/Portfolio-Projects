#!/usr/bin/env python3
"""make resume — undoes infra/pause.py: starts MySQL back up and restores
Container Apps to their normal scale range (min=0, max=3) so they can serve
traffic again (Consumption plan scale-to-zero still applies when idle).

Safe to run even if nothing was paused (MySQL start / containerapp update
are no-ops against an already-running resource).
"""
import json
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
STATE_FILE = REPO_ROOT / "infra" / ".state.json"

MAX_REPLICAS_DEFAULT = "3"


def _wait_for_mysql_ready(mysql_name: str, resource_group: str, timeout: float = 180.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        result = subprocess.run(
            ["az", "mysql", "flexible-server", "show", "--name", mysql_name,
             "--resource-group", resource_group, "--query", "state", "-o", "tsv"],
            capture_output=True, text=True,
        )
        state = result.stdout.strip()
        print(f"  MySQL state: {state or 'unknown'}")
        if state == "Ready":
            return True
        time.sleep(10)
    return False


def main() -> int:
    if not STATE_FILE.exists():
        print("No infra/.state.json found — nothing to resume (or provision.py was never run).")
        return 0

    state = json.loads(STATE_FILE.read_text())
    resource_group = state["resource_group"]
    mysql_name = state["names"]["mysql_server_name"]

    print(f"=== Starting MySQL Flexible Server '{mysql_name}' ===")
    result = subprocess.run(
        ["az", "mysql", "flexible-server", "start", "--name", mysql_name,
         "--resource-group", resource_group, "--output", "json"],
    )
    if result.returncode != 0:
        print("MySQL start failed — check `az mysql flexible-server show` for its current state.")
        return 1

    print("Waiting for MySQL to report Ready...")
    if not _wait_for_mysql_ready(mysql_name, resource_group):
        print("MySQL did not reach Ready within the timeout — check `az mysql flexible-server show` manually.")
        return 1

    container_apps = state.get("container_apps", {})
    for app_name in container_apps.values():
        if app_name == "bff":
            # bff holds the live migration's state in an in-process
            # singleton (see migration_engine.py) — pinned to exactly one
            # replica always. Caught for real: letting it scale out let two
            # replicas each run their own independent copy of the migration,
            # producing an impossible-looking mixed step state as traffic
            # load-balanced between them.
            print("=== Restoring Container App 'bff' scale range (min=1, max=1 — pinned, see migration_engine.py) ===")
            subprocess.run(
                ["az", "containerapp", "update", "--name", app_name, "--resource-group", resource_group,
                 "--min-replicas", "1", "--max-replicas", "1", "--output", "json"],
            )
            continue
        print(f"=== Restoring Container App '{app_name}' scale range (min=0, max={MAX_REPLICAS_DEFAULT}) ===")
        subprocess.run(
            ["az", "containerapp", "update", "--name", app_name, "--resource-group", resource_group,
             "--min-replicas", "0", "--max-replicas", MAX_REPLICAS_DEFAULT, "--output", "json"],
        )

    print("\nResumed. Give the monolith/bff a few seconds to cold-start on first request.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

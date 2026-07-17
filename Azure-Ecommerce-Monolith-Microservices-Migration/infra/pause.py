#!/usr/bin/env python3
"""make pause — stops the resources that bill while idle, without deleting anything.

MySQL Flexible Server is the only resource in this stack that bills 24/7
regardless of traffic (Container Apps on the Consumption plan already scale
to zero on their own after a few idle minutes). `az mysql flexible-server
stop` pauses compute billing for up to 7 days, after which Azure
auto-restarts it — `make resume` (infra/resume.py) starts it back up early
and explicitly scales every known Container App to 0 so nothing is left
serving traffic (and being billed) while paused.

Safe to run repeatedly; does not touch infra/.state.json.
"""
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
STATE_FILE = REPO_ROOT / "infra" / ".state.json"


def main() -> int:
    if not STATE_FILE.exists():
        print("No infra/.state.json found — nothing to pause (or provision.py was never run).")
        return 0

    state = json.loads(STATE_FILE.read_text())
    resource_group = state["resource_group"]
    mysql_name = state["names"]["mysql_server_name"]

    print(f"=== Stopping MySQL Flexible Server '{mysql_name}' (bills 24/7 while running) ===")
    result = subprocess.run(
        ["az", "mysql", "flexible-server", "stop", "--name", mysql_name,
         "--resource-group", resource_group, "--output", "json"],
    )
    if result.returncode != 0:
        print("MySQL stop failed — check `az mysql flexible-server show` for its current state.")
        return 1

    container_apps = state.get("container_apps", {})
    for app_name in container_apps.values():
        print(f"=== Scaling Container App '{app_name}' to 0 replicas ===")
        subprocess.run(
            ["az", "containerapp", "update", "--name", app_name, "--resource-group", resource_group,
             "--min-replicas", "0", "--max-replicas", "0", "--output", "json"],
        )

    print("\nPaused. MySQL auto-resumes after 7 days if you forget — run `make resume` before then.")
    print("Note: Azure still bills ACR (flat monthly) and Log Analytics (per-GB) while paused; those are near-zero for this project's traffic.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

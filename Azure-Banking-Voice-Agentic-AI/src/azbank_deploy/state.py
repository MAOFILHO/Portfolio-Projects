"""`deployment_state.json` -- a checkpoint, not the truth. Resume discipline (`CLAUDE.md`): this
project has already been burned once by trusting a doc over the live API (a resume that found
`Microsoft.Communication` already `Registered` while `PROJECT_STATE.md` still said `Registering`).
`resume_state()` is what makes that discipline mechanical here: it starts from the checkpoint file,
then asks Azure directly about every resource, and lets the live answer win on any disagreement.
"""
from __future__ import annotations

import json
from pathlib import Path

from . import az_cli
from .resources import ORDER, RESOURCES, initial_state

DEFAULT_STATE_FILE = Path(__file__).resolve().parent / "deployment_state.json"


def load(path: Path = DEFAULT_STATE_FILE) -> dict[str, str]:
    if not path.exists():
        return initial_state()
    raw = json.loads(path.read_text())
    # Tolerate a checkpoint written against an older graph shape (a resource added or removed
    # since): unknown keys are dropped, missing keys default to absent, rather than erroring.
    return {key: raw.get(key, "absent") for key in ORDER}


def save(state: dict[str, str], path: Path = DEFAULT_STATE_FILE) -> None:
    path.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n")


def probe_live_state(resource_group: str, names: dict[str, str]) -> dict[str, str]:
    """The true state, read from Azure directly -- one existence check per resource. `names` maps
    each resource key to its Azure resource name (the CLI's config owns this; kept out of
    resources.py, which stays pure)."""
    checks = {
        "app_insights": lambda: az_cli.app_insights_exists(resource_group, names["app_insights"]),
        "container_apps_env": lambda: az_cli.container_app_env_exists(resource_group, names["container_apps_env"]),
        "call_records_account": lambda: az_cli.storage_account_exists(resource_group, names["call_records_account"]),
        "mock_core_banking": lambda: az_cli.container_app_exists(resource_group, names["mock_core_banking"]),
        "acs": lambda: az_cli.acs_exists(resource_group, names["acs"]),
        "voice_agent": lambda: az_cli.container_app_exists(resource_group, names["voice_agent"]),
        "call_records_rbac": lambda: az_cli.call_records_rbac_present(resource_group, names["call_records_account"]),
        "aoai": lambda: az_cli.cognitive_services_account_exists(resource_group, names["aoai"]),
    }
    return {key: ("deployed" if checks[key]() else "absent") for key in ORDER}


def resume_state(resource_group: str, names: dict[str, str], path: Path = DEFAULT_STATE_FILE) -> dict[str, str]:
    """The checkpoint reconciled against live Azure. Live always wins -- a resource the checkpoint
    thinks is deployed but Azure says is gone is treated as absent, and vice versa, with a warning on
    every disagreement so a stale checkpoint is visible, not silent."""
    checkpoint = load(path)
    live = probe_live_state(resource_group, names)
    for key in ORDER:
        if checkpoint[key] != live[key]:
            print(
                f"resume: {RESOURCES[key].label} -- checkpoint said {checkpoint[key]!r}, "
                f"live Azure says {live[key]!r}. Trusting live."
            )
    save(live, path)
    return live

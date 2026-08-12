"""Append-only, file-backed log of fine-tune job status polls.

Persisted to disk — not held only in a single SSE connection's memory — so
the event history survives page refreshes and backend restarts. A background
poller (see api/routes/finetune.py) owns writing to this log independently of
any browser connection; SSE handlers only read from it.
"""

import json
from pathlib import Path
from typing import Any

ARTIFACTS_DIR = Path("artifacts")


def _log_path(scenario_id: str) -> Path:
    scenario_dir = ARTIFACTS_DIR / scenario_id
    scenario_dir.mkdir(parents=True, exist_ok=True)
    return scenario_dir / "job_events.jsonl"


def append_event(scenario_id: str, event: dict[str, Any]) -> None:
    with _log_path(scenario_id).open("a") as f:
        f.write(json.dumps(event) + "\n")


def read_events(scenario_id: str) -> list[dict[str, Any]]:
    path = _log_path(scenario_id)
    if not path.exists():
        return []
    with path.open() as f:
        return [json.loads(line) for line in f if line.strip()]


def _active_job_path(scenario_id: str) -> Path:
    return ARTIFACTS_DIR / scenario_id / "active_job.json"


def read_active_job_override(scenario_id: str) -> str | None:
    """Job identifier to track for this scenario, if it differs from the
    default `{project_suffix}-{scenario_id}-ft` naming — e.g. after a manual
    stop+retry under a new job name, since Bedrock never releases a job name
    once used, even for a stopped job."""
    path = _active_job_path(scenario_id)
    if not path.exists():
        return None
    job_name = json.loads(path.read_text()).get("job_name")
    return str(job_name) if job_name is not None else None


def write_active_job_override(scenario_id: str, job_name: str) -> None:
    path = _active_job_path(scenario_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"job_name": job_name}))

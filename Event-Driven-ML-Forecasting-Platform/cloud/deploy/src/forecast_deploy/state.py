"""Resumable deployment state: a JSON checkpoint tracking which steps have
succeeded, so a failed `deploy` run can be re-invoked and pick up where it
left off. Ported from
Azure-Agentic-Video-Surveillance/src/surveil_deploy/state.py verbatim.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel, Field


class StepRecord(BaseModel):
    name: str
    completed_at: str
    outputs: dict = Field(default_factory=dict)


class DeploymentState(BaseModel):
    completed_steps: dict[str, StepRecord] = Field(default_factory=dict)
    resource_outputs: dict[str, str] = Field(default_factory=dict)

    def is_complete(self, step_name: str) -> bool:
        return step_name in self.completed_steps

    def mark_complete(self, step_name: str, outputs: dict | None = None) -> None:
        self.completed_steps[step_name] = StepRecord(
            name=step_name,
            completed_at=datetime.now(timezone.utc).isoformat(),
            outputs=outputs or {},
        )
        if outputs:
            self.resource_outputs.update({k: str(v) for k, v in outputs.items()})

    def reset(self) -> None:
        self.completed_steps.clear()
        self.resource_outputs.clear()


def load_state(path: Path) -> DeploymentState:
    if not path.exists():
        return DeploymentState()
    try:
        return DeploymentState.model_validate(json.loads(path.read_text()))
    except (json.JSONDecodeError, ValueError):
        return DeploymentState()


def save_state(path: Path, state: DeploymentState) -> None:
    path.write_text(state.model_dump_json(indent=2))


def delete_state(path: Path) -> None:
    if path.exists():
        path.unlink()

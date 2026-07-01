"""Deployment state persistence for resumable deployments."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class StepRecord:
    name: str
    status: str = "pending"  # pending | completed | failed
    started_at: str | None = None
    completed_at: str | None = None
    error: str | None = None
    outputs: dict = field(default_factory=dict)


@dataclass
class DeploymentState:
    steps: dict[str, StepRecord] = field(default_factory=dict)
    resource_group: str = ""
    location: str = ""
    subscription_id: str = ""
    deployed_resources: dict = field(default_factory=dict)
    created_at: str = ""
    updated_at: str = ""

    _path: Path | None = field(default=None, repr=False)

    @classmethod
    def load(cls, path: Path) -> DeploymentState:
        if path.exists():
            data = json.loads(path.read_text())
            steps = {k: StepRecord(**v) for k, v in data.get("steps", {}).items()}
            state = cls(
                steps=steps,
                resource_group=data.get("resource_group", ""),
                location=data.get("location", ""),
                subscription_id=data.get("subscription_id", ""),
                deployed_resources=data.get("deployed_resources", {}),
                created_at=data.get("created_at", ""),
                updated_at=data.get("updated_at", ""),
            )
        else:
            state = cls(created_at=_now())
        state._path = path
        return state

    def save(self) -> None:
        if self._path is None:
            return
        self.updated_at = _now()
        data = {
            "steps": {k: _step_dict(v) for k, v in self.steps.items()},
            "resource_group": self.resource_group,
            "location": self.location,
            "subscription_id": self.subscription_id,
            "deployed_resources": self.deployed_resources,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
        self._path.write_text(json.dumps(data, indent=2) + "\n")

    def is_completed(self, step_name: str) -> bool:
        rec = self.steps.get(step_name)
        return rec is not None and rec.status == "completed"

    def mark_started(self, step_name: str) -> None:
        self.steps[step_name] = StepRecord(
            name=step_name, status="in_progress", started_at=_now()
        )
        self.save()

    def mark_completed(self, step_name: str, outputs: dict | None = None) -> None:
        rec = self.steps.get(step_name, StepRecord(name=step_name))
        rec.status = "completed"
        rec.completed_at = _now()
        if outputs:
            rec.outputs = outputs
        self.steps[step_name] = rec
        self.save()

    def mark_failed(self, step_name: str, error: str) -> None:
        rec = self.steps.get(step_name, StepRecord(name=step_name))
        rec.status = "failed"
        rec.error = error
        self.steps[step_name] = rec
        self.save()

    def update_resources(self, resources: dict) -> None:
        self.deployed_resources.update(resources)
        self.save()

    def reset(self) -> None:
        self.steps.clear()
        self.deployed_resources.clear()
        self.created_at = _now()
        self.save()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _step_dict(rec: StepRecord) -> dict:
    return {
        "name": rec.name,
        "status": rec.status,
        "started_at": rec.started_at,
        "completed_at": rec.completed_at,
        "error": rec.error,
        "outputs": rec.outputs,
    }

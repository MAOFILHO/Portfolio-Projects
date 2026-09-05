"""Task discovery for the Stateful Session Server module.

Shared by both the baseline (server_baseline) and pattern (server_session)
services: they run the identical task set, so both service definitions
point at this one class.
"""

from pathlib import Path

from src.base.task_manager import BaseTaskManager


class StatefulSessionTaskManager(BaseTaskManager):
    def __init__(self, task_suite: str = "standard"):
        super().__init__(
            tasks_root=Path("tasks"),
            mcp_service="stateful_session",
            task_organization="directory",
            task_suite=task_suite,
        )

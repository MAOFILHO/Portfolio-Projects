"""Task discovery for the Tool Orchestrator module.

Shared by both the control (server_wrapper) and pattern (server_orchestrator)
services: they run the identical task set, so both service definitions point
at this one class.
"""

from pathlib import Path

from src.base.task_manager import BaseTaskManager


class ToolOrchestratorTaskManager(BaseTaskManager):
    def __init__(self, task_suite: str = "standard"):
        super().__init__(
            tasks_root=Path("tasks"),
            mcp_service="tool_orchestrator",
            task_organization="directory",
            task_suite=task_suite,
        )

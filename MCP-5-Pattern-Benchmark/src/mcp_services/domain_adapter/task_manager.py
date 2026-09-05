"""Task discovery for the Domain-Specific Adapter module.

Shared by both the baseline (domain_wrapper, reusing server_wrapper) and
pattern (domain_adapter) services: they run the identical task set, so both
service definitions point at this one class.
"""

from pathlib import Path

from src.base.task_manager import BaseTaskManager


class DomainAdapterTaskManager(BaseTaskManager):
    def __init__(self, task_suite: str = "standard"):
        super().__init__(
            tasks_root=Path("tasks"),
            mcp_service="domain_adapter",
            task_organization="directory",
            task_suite=task_suite,
        )

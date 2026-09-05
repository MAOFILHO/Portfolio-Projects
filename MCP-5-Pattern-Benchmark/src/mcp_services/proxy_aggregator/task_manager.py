"""Task discovery for the Proxy Aggregator module.

Shared by both the control (server_wrapper, service "proxy_wrapper") and
pattern (server_proxy_aggregator) services: they run the identical task set,
so both service definitions point at this one class.
"""

from pathlib import Path

from src.base.task_manager import BaseTaskManager


class ProxyAggregatorTaskManager(BaseTaskManager):
    def __init__(self, task_suite: str = "standard"):
        super().__init__(
            tasks_root=Path("tasks"),
            mcp_service="proxy_aggregator",
            task_organization="directory",
            task_suite=task_suite,
        )

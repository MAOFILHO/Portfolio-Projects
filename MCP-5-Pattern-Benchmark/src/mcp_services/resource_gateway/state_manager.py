"""State management for the Resource Gateway module.

Resets and reloads the Postgres backend before each task. Both services
(control and pattern) share this one class since they front the same
backend.
"""

import os
from typing import Any, Dict, Optional

from backend.seed import reset_and_seed
from src.base.state_manager import BaseStateManager, InitialStateInfo
from src.base.task_manager import BaseTask


class ResourceGatewayStateManager(BaseStateManager):
    def __init__(self):
        super().__init__(service_name="resource_gateway")

    def _create_initial_state(self, task: BaseTask) -> Optional[InitialStateInfo]:
        reset_and_seed(os.environ["DATABASE_URL"])
        return InitialStateInfo(state_id="seeded")

    def _store_initial_state_info(self, task: BaseTask, state_info: InitialStateInfo) -> None:
        pass

    def _cleanup_task_initial_state(self, task: BaseTask) -> bool:
        return True

    def _cleanup_single_resource(self, resource: Dict[str, Any]) -> bool:
        return True

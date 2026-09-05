"""State management for the Domain-Specific Adapter module.

Resets and reloads the same Postgres backend as Tool Orchestrator, since both
modules front the same /tickets namespace. Both services (domain_wrapper and
domain_adapter) share this one class.
"""

import os
from typing import Any, Dict, Optional

from backend.seed import reset_and_seed
from src.base.state_manager import BaseStateManager, InitialStateInfo
from src.base.task_manager import BaseTask


class DomainAdapterStateManager(BaseStateManager):
    def __init__(self):
        super().__init__(service_name="domain_adapter")

    def _create_initial_state(self, task: BaseTask) -> Optional[InitialStateInfo]:
        reset_and_seed(os.environ["DATABASE_URL"])
        return InitialStateInfo(state_id="seeded")

    def _store_initial_state_info(self, task: BaseTask, state_info: InitialStateInfo) -> None:
        pass

    def _cleanup_task_initial_state(self, task: BaseTask) -> bool:
        return True

    def _cleanup_single_resource(self, resource: Dict[str, Any]) -> bool:
        return True

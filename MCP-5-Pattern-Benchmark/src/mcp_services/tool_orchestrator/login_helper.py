"""Login helper for the Tool Orchestrator module.

The backend is synthetic and unauthenticated, so there's nothing to log
into. Required only because the factory instantiates one for every service.
"""

from src.base.login_helper import BaseLoginHelper


class ToolOrchestratorLoginHelper(BaseLoginHelper):
    def login(self, **kwargs):
        return True

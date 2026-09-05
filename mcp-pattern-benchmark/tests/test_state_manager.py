"""Tests for ToolOrchestratorStateManager: set_up must seed the real backend
before a task runs (the harness's Stage 1, src/evaluator.py's set_up call).
"""

from src.mcp_services.proxy_aggregator.state_manager import ProxyAggregatorStateManager
from src.mcp_services.proxy_aggregator.task_manager import ProxyAggregatorTaskManager
from src.mcp_services.tool_orchestrator.state_manager import ToolOrchestratorStateManager
from src.mcp_services.tool_orchestrator.task_manager import ToolOrchestratorTaskManager
from tasks.utils.backend_state import get_runbook, get_ticket


def test_set_up_seeds_the_real_backend(db):
    task = ToolOrchestratorTaskManager().filter_tasks("all")[0]

    success = ToolOrchestratorStateManager().set_up(task)

    assert success
    assert get_ticket(1) == {
        "id": 1,
        "title": "Printer not connecting to network",
        "status": "open",
        "assignee": None,
    }


def test_proxy_aggregator_set_up_seeds_the_real_backend(db):
    task = ProxyAggregatorTaskManager().filter_tasks("all")[0]

    success = ProxyAggregatorStateManager().set_up(task)

    assert success
    assert get_runbook(1) == {
        "id": 1,
        "repo_id": 1,
        "title": "Rolling back a bad billing deploy",
        "body": "1. Halt traffic. 2. Redeploy last tag.",
        "internal_notes": (
            "Escalate to payments-oncall before rolling back; "
            "past rollbacks corrupted the ledger."
        ),
    }

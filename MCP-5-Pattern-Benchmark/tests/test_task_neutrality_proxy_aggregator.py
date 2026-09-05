"""Repo-hygiene gate: fails the build if any proxy_aggregator task's
instruction file names a tool from either server, so neutrality can't
silently regress as tasks are edited.

server_proxy_aggregator's real tool names are just discover_tools/call_tool,
so the identifying strings that matter for this server are the service
namespaces it dispatches to (repos/runbooks/deploys) and their distinctive
per-service operation names. Generic bare verbs (get/list/create) are
excluded: they're common English words, and checking them would flag normal
task prose as a false positive rather than catch a real leak.
"""

import asyncio
from pathlib import Path

from src.mcp_services.proxy_aggregator.server_proxy_aggregator import _OPERATIONS
from src.mcp_services.proxy_aggregator.server_proxy_aggregator import mcp as aggregator_mcp
from src.mcp_services.tool_orchestrator.server_wrapper import mcp as wrapper_mcp

TASKS_ROOT = Path(__file__).resolve().parent.parent / "tasks/proxy_aggregator/standard"


def _tool_names(mcp) -> list[str]:
    return [tool.name for tool in asyncio.run(mcp.list_tools())]


def test_no_task_description_names_a_tool_from_either_server():
    tool_names = (
        _tool_names(wrapper_mcp)
        + _tool_names(aggregator_mcp)
        + list(_OPERATIONS.keys())
        + ["get_change_request", "update_status"]
    )

    violations = [
        (description_path, name)
        for description_path in TASKS_ROOT.glob("*/*/description.md")
        for name in tool_names
        if name in description_path.read_text()
    ]

    assert violations == []

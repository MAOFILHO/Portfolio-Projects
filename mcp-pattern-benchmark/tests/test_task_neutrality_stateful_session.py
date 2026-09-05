"""Repo-hygiene gate: fails the build if any stateful_session task's
instruction file names a tool from either server, so neutrality can't
silently regress as tasks are edited.
"""

import asyncio
from pathlib import Path

from src.mcp_services.stateful_session.server_baseline import mcp as baseline_mcp
from src.mcp_services.stateful_session.server_session import mcp as pattern_mcp

TASKS_ROOT = Path(__file__).resolve().parent.parent / "tasks/stateful_session/standard"


def _tool_names(mcp) -> list[str]:
    return [tool.name for tool in asyncio.run(mcp.list_tools())]


def test_no_task_description_names_a_tool_from_either_server():
    tool_names = _tool_names(baseline_mcp) + _tool_names(pattern_mcp)

    violations = [
        (description_path, name)
        for description_path in TASKS_ROOT.glob("*/*/description.md")
        for name in tool_names
        if name in description_path.read_text()
    ]

    assert violations == []

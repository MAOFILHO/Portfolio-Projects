"""Tests for the Proxy Aggregator pattern server (server_proxy_aggregator).

Drives the server's tools through a real MCP ClientSession, in-memory,
exactly the interface the agent calls through. Its static surface is exactly
two tools -- discover_tools and call_tool -- which dispatch to the real
backend, backed by a real (throwaway) Postgres -- no subprocess, no LLM, no
mocking. Same seam as test_server_wrapper.py.
"""

import httpx
import pytest
from mcp.shared.memory import create_connected_server_and_client_session

from backend.app import app as backend_app
from backend.seed import reset_and_seed
from src.mcp_services.proxy_aggregator import server_proxy_aggregator
from src.mcp_services.proxy_aggregator.server_proxy_aggregator import mcp

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def wrapped_mcp(db, monkeypatch):
    """Point server_proxy_aggregator's HTTP client at the real API in-process,
    backed by the real (seeded) test Postgres."""
    reset_and_seed(db)
    transport = httpx.ASGITransport(app=backend_app)
    monkeypatch.setattr(
        server_proxy_aggregator,
        "client",
        httpx.AsyncClient(transport=transport, base_url="http://testserver"),
    )
    return mcp


async def call(mcp_instance, tool_name: str, arguments: dict | None = None):
    """Call a tool through a real in-memory MCP session and return its
    structured result (the same data an agent's client receives)."""
    async with create_connected_server_and_client_session(mcp_instance) as session:
        result = await session.call_tool(tool_name, arguments or {})
        assert not result.isError, result.content
        return result.structuredContent


async def test_discover_tools_with_no_service_lists_the_available_services(wrapped_mcp):
    services = (await call(wrapped_mcp, "discover_tools", {}))["result"]

    assert set(services) == {"repos", "runbooks", "deploys"}


async def test_discover_tools_returns_the_runbooks_operations(wrapped_mcp):
    operations = (await call(wrapped_mcp, "discover_tools", {"service": "runbooks"}))["result"]

    assert operations == [
        {"name": "list", "description": "List runbooks for a repo.", "parameters": ["repo_id"]},
        {"name": "get", "description": "Get one runbook by id.", "parameters": ["runbook_id"]},
    ]


async def test_call_tool_dispatches_runbooks_get_to_the_real_backend(wrapped_mcp):
    runbook = (
        await call(
            wrapped_mcp, "call_tool", {"service": "runbooks", "tool": "get", "args": {"runbook_id": 1}}
        )
    )["result"]

    assert runbook == {
        "id": 1,
        "repo_id": 1,
        "title": "Rolling back a bad billing deploy",
        "body": "1. Halt traffic. 2. Redeploy last tag.",
        "internal_notes": (
            "Escalate to payments-oncall before rolling back; "
            "past rollbacks corrupted the ledger."
        ),
    }


async def test_call_tool_dispatches_runbooks_list_to_the_real_backend(wrapped_mcp):
    runbooks = (
        await call(wrapped_mcp, "call_tool", {"service": "runbooks", "tool": "list", "args": {"repo_id": 1}})
    )["result"]

    assert [r["id"] for r in runbooks] == [1, 2]


async def test_discover_tools_returns_the_deploys_operations(wrapped_mcp):
    operations = (await call(wrapped_mcp, "discover_tools", {"service": "deploys"}))["result"]

    assert operations == [
        {
            "name": "create",
            "description": "Create a pending deploy.",
            "parameters": ["repo_id", "environment"],
        },
        {"name": "get", "description": "Get one deploy by id.", "parameters": ["deploy_id"]},
        {
            "name": "update_status",
            "description": "Update a deploy's status.",
            "parameters": ["deploy_id", "status"],
        },
    ]


async def test_call_tool_dispatches_deploys_create_to_the_real_backend(wrapped_mcp):
    deploy = (
        await call(
            wrapped_mcp,
            "call_tool",
            {"service": "deploys", "tool": "create", "args": {"repo_id": 1, "environment": "production"}},
        )
    )["result"]

    assert deploy == {"id": 1, "repo_id": 1, "environment": "production", "status": "pending"}


async def test_call_tool_dispatches_deploys_get_to_the_real_backend(wrapped_mcp):
    created = (
        await call(
            wrapped_mcp,
            "call_tool",
            {"service": "deploys", "tool": "create", "args": {"repo_id": 1, "environment": "staging"}},
        )
    )["result"]

    deploy = (
        await call(
            wrapped_mcp, "call_tool", {"service": "deploys", "tool": "get", "args": {"deploy_id": created["id"]}}
        )
    )["result"]

    assert deploy == created


async def test_call_tool_dispatches_deploys_update_status_to_the_real_backend(wrapped_mcp):
    created = (
        await call(
            wrapped_mcp,
            "call_tool",
            {"service": "deploys", "tool": "create", "args": {"repo_id": 1, "environment": "production"}},
        )
    )["result"]

    deploy = (
        await call(
            wrapped_mcp,
            "call_tool",
            {
                "service": "deploys",
                "tool": "update_status",
                "args": {"deploy_id": created["id"], "status": "succeeded"},
            },
        )
    )["result"]

    assert deploy == {**created, "status": "succeeded"}


async def test_discover_tools_returns_the_repos_operations(wrapped_mcp):
    operations = (await call(wrapped_mcp, "discover_tools", {"service": "repos"}))["result"]

    assert operations == [
        {
            "name": "get_change_request",
            "description": "Get one change request by id.",
            "parameters": ["change_request_id"],
        },
    ]


async def test_call_tool_dispatches_repos_get_change_request_to_the_real_backend(wrapped_mcp):
    change_request = (
        await call(
            wrapped_mcp,
            "call_tool",
            {"service": "repos", "tool": "get_change_request", "args": {"change_request_id": 1}},
        )
    )["result"]

    assert change_request == {
        "id": 1,
        "repo_id": 1,
        "title": "Fix rounding error in invoice totals",
        "diff": "--- a/invoice.py\n+++ b/invoice.py\n",
        "status": "open",
    }


async def test_discover_tools_reports_an_unknown_service_with_the_valid_ones(wrapped_mcp):
    async with create_connected_server_and_client_session(wrapped_mcp) as session:
        result = await session.call_tool("discover_tools", {"service": "version-control"})

    assert result.isError
    text = result.content[0].text
    assert "version-control" in text
    assert "repos" in text and "runbooks" in text and "deploys" in text


async def test_call_tool_reports_an_unknown_service_with_the_valid_ones(wrapped_mcp):
    async with create_connected_server_and_client_session(wrapped_mcp) as session:
        result = await session.call_tool(
            "call_tool", {"service": "version-control", "tool": "list", "args": {}}
        )

    assert result.isError
    text = result.content[0].text
    assert "version-control" in text
    assert "repos" in text and "runbooks" in text and "deploys" in text

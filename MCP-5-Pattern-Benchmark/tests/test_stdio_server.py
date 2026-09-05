"""Tests for MCPStdioServer's resource support.

A real, subprocess-backed connection to a minimal fixture MCP server
(tests/mcp_resource_fixture_server.py) exposing one resource -- no mocks,
no dependency on this project's own backend or pattern servers. This is the
harness's own client wrapper, so this is the first test to exercise it
directly rather than only through a full pipeline run.
"""

import sys

import pytest

from src.agents.mcp.stdio_server import MCPStdioServer

pytestmark = pytest.mark.anyio

FIXTURE_ARGS = ["-m", "tests.mcp_resource_fixture_server"]


@pytest.fixture
def anyio_backend():
    return "asyncio"


async def test_list_resources_returns_the_fixture_servers_one_resource():
    async with MCPStdioServer(command=sys.executable, args=FIXTURE_ARGS) as server:
        resources = await server.list_resources()

    assert len(resources) == 1
    assert str(resources[0]["uri"]) == "fixture://hello"


async def test_read_resource_returns_the_fixture_servers_content():
    async with MCPStdioServer(command=sys.executable, args=FIXTURE_ARGS) as server:
        result = await server.read_resource("fixture://hello")

    assert result["contents"][0]["text"] == "hello from fixture resource"


async def test_list_resource_templates_returns_the_fixture_servers_one_template():
    async with MCPStdioServer(command=sys.executable, args=FIXTURE_ARGS) as server:
        templates = await server.list_resource_templates()

    assert len(templates) == 1
    assert templates[0]["uriTemplate"] == "fixture://{item_id}"


async def test_read_resource_reads_a_template_resource_by_its_filled_in_uri():
    async with MCPStdioServer(command=sys.executable, args=FIXTURE_ARGS) as server:
        result = await server.read_resource("fixture://42")

    assert result["contents"][0]["text"] == "fixture item 42"

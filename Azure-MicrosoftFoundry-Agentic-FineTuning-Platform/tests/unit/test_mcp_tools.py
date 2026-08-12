"""Unit tests for the MCP tool registry and servers, in mock mode.

Exercises the same registry the LangGraph agents call through
(app.mcp_clients.registry), not the servers' internals directly — this is
what actually gets invoked in production.
"""

from __future__ import annotations

import pytest

from app.mcp_clients.registry import call_tool, list_tools


@pytest.mark.asyncio
async def test_list_tools_returns_19_tools_across_3_servers():
    tools = await list_tools()
    assert len(tools) == 19
    servers = {t.server for t in tools}
    assert servers == {"catalog", "finetune", "inference"}


@pytest.mark.asyncio
async def test_every_tool_has_a_name_and_description():
    tools = await list_tools()
    for tool in tools:
        assert tool.name
        assert tool.description


@pytest.mark.asyncio
async def test_list_models_returns_catalog():
    result = await call_tool("list_models")
    assert result["count"] >= 1
    assert all("name" in m for m in result["models"])


@pytest.mark.asyncio
async def test_get_leaderboard_winner_honours_metric_direction():
    # safety_attack_success_rate: lower is better.
    board = await call_tool("get_leaderboard", {"metric": "safety_attack_success_rate"})
    winner_row = next(r for r in board["rows"] if r["model_name"] == board["winner"])
    assert all(
        winner_row["safety_attack_success_rate"] <= r["safety_attack_success_rate"]
        for r in board["rows"]
    )


@pytest.mark.asyncio
async def test_validate_jsonl_reports_ten_valid_rows():
    result = await call_tool("validate_jsonl", {})
    assert result["is_valid"] is True
    assert result["valid_rows"] == 10
    assert result["total_lines"] == 10


@pytest.mark.asyncio
async def test_estimate_training_cost_matches_lab_figures():
    # Global tier, 16,000 billed tokens -> the lab's own stated $0.032.
    global_estimate = await call_tool(
        "estimate_training_cost", {"billed_tokens": 16000, "training_type": "Global"}
    )
    assert global_estimate["estimated_usd"] == pytest.approx(0.032, abs=0.001)

    # Developer tier is 50% off -> $0.016.
    dev_estimate = await call_tool(
        "estimate_training_cost", {"billed_tokens": 16000, "training_type": "Developer"}
    )
    assert dev_estimate["estimated_usd"] == pytest.approx(0.016, abs=0.001)


@pytest.mark.asyncio
async def test_deploy_finetuned_model_warns_on_standard_sku():
    result = await call_tool("deploy_finetuned_model", {"deployment_type": "Standard"})
    assert result["hourly_cost_usd"] > 0
    assert result["warning"] is not None
    assert "1,224" in result["warning"] or "1224" in result["warning"]


@pytest.mark.asyncio
async def test_deploy_finetuned_model_developer_tier_is_free():
    result = await call_tool("deploy_finetuned_model", {"deployment_type": "Developer"})
    assert result["hourly_cost_usd"] == 0.0
    assert result["warning"] is None


@pytest.mark.asyncio
async def test_unknown_tool_raises():
    with pytest.raises(Exception):
        await call_tool("not_a_real_tool", {})

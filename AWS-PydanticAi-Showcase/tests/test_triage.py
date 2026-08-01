"""Support Triage Copilot — offline tests.

The two things worth pinning down: the discriminated union round-trips through
JSON as the *right branch* (not a bag of optional fields), and the tools really
do read injected deps rather than a module-level global.
"""

from __future__ import annotations

import pytest
from pydantic import TypeAdapter
from pydantic_ai import ModelResponse, ToolCallPart
from pydantic_ai.models.function import AgentInfo, FunctionModel
from pydantic_ai.models.test import TestModel

from app.demos.triage.agents import triage_agent
from app.demos.triage.models import (
    Account,
    Escalate,
    NeedsInfo,
    PastTicket,
    Resolve,
    TriageDecision,
    TriageDeps,
)
from app.demos.triage.router import RESULT_CACHE
from tests.test_main import client  # noqa: F401 - fixture


@pytest.fixture(autouse=True)
def clear_cache():
    RESULT_CACHE.clear()
    yield


def decision_model(payload: dict) -> FunctionModel:
    """A model that answers with one fixed decision, after using every tool once.

    Calling the tools first is what makes this a test of the DI seam: if the
    tools couldn't reach `ctx.deps`, the run would fail before the output tool.

    Note the output-tool lookup: because `TriageDecision` is a union, Pydantic AI
    generates one output tool per member (`final_result_Resolve`,
    `final_result_Escalate`, ...) rather than a single tool taking a
    discriminator, so the branch is chosen by *which tool is called*.
    """
    state = {"used_tools": False}
    expected_suffix = {
        "resolve": "Resolve",
        "escalate": "Escalate",
        "needs_info": "NeedsInfo",
    }[payload["action"]]

    def respond(messages: list, info: AgentInfo) -> ModelResponse:
        if not state["used_tools"]:
            state["used_tools"] = True
            return ModelResponse(
                parts=[
                    ToolCallPart(tool_name="lookup_account", args={}),
                    ToolCallPart(tool_name="recent_tickets", args={}),
                    ToolCallPart(tool_name="check_entitlement", args={"feature": "sso"}),
                ]
            )
        tool = next(t for t in info.output_tools if t.name.endswith(expected_suffix))
        return ModelResponse(parts=[ToolCallPart(tool_name=tool.name, args=payload)])

    return FunctionModel(respond)


DEPS = TriageDeps(
    account_id="ACC-1001",
    accounts={
        "ACC-1001": Account(
            account_id="ACC-1001",
            company="Northwind Traders",
            plan="enterprise",
            seats=2400,
            monthly_spend_usd=48000,
            support_sla_hours=1,
            open_incidents=2,
        )
    },
    tickets={
        "ACC-1001": [
            PastTicket(ticket_id="T-1", subject="5xx on ingest", resolved=False, days_ago=1)
        ]
    },
)


@pytest.mark.parametrize(
    ("payload", "expected_type"),
    [
        (
            {"action": "resolve", "draft_reply": "Settings > Profile > Email.", "confidence": 0.9},
            Resolve,
        ),
        (
            {
                "action": "escalate",
                "team": "infrastructure",
                "severity": "critical",
                "reason": "Region-wide 503s against a 1h SLA.",
            },
            Escalate,
        ),
        (
            {"action": "needs_info", "questions": ["Which dashboard?", "Which date range?"]},
            NeedsInfo,
        ),
    ],
)
async def test_each_union_branch_is_produced_and_typed(payload: dict, expected_type: type):
    with triage_agent.override(model=decision_model(payload)):
        result = await triage_agent.run("A ticket", deps=DEPS)

    assert isinstance(result.output, expected_type)


async def test_union_round_trips_through_json_as_the_right_branch():
    """The discriminator, not field-sniffing, is what picks the branch back up."""
    payload = {
        "action": "escalate",
        "team": "security",
        "severity": "high",
        "reason": "Possible credential leak.",
    }
    with triage_agent.override(model=decision_model(payload)):
        result = await triage_agent.run("A ticket", deps=DEPS)

    adapter = TypeAdapter(TriageDecision)
    restored = adapter.validate_json(adapter.dump_json(result.output))
    assert isinstance(restored, Escalate)
    assert restored.team == "security"


async def test_tools_read_the_injected_deps_not_a_global():
    """Point the same agent at a different tenant and the tool output follows."""
    other = TriageDeps(
        account_id="ACC-9999",
        accounts={
            "ACC-9999": Account(
                account_id="ACC-9999",
                company="Fabrikam Inc.",
                plan="free",
                seats=3,
                monthly_spend_usd=0,
                support_sla_hours=72,
            )
        },
    )

    payload = {"action": "resolve", "draft_reply": "ok", "confidence": 0.5}
    with triage_agent.override(model=decision_model(payload)):
        result = await triage_agent.run("A ticket", deps=other)

    rendered = str(result.all_messages())
    assert "Fabrikam" in rendered
    assert "Northwind" not in rendered
    # The free plan doesn't include SSO; the entitlement tool must say so.
    assert "NOT included in the free plan" in rendered


async def test_classify_endpoint_returns_the_decision_and_the_tool_trace(client):  # noqa: F811
    payload = {
        "action": "escalate",
        "team": "infrastructure",
        "severity": "critical",
        "reason": "Region-wide outage.",
    }
    with triage_agent.override(model=decision_model(payload)):
        response = client.post(
            "/api/triage/classify",
            json={"account_id": "ACC-1001", "ticket": "Production is down across eu-west-1."},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["decision"]["action"] == "escalate"
    assert body["decision"]["team"] == "infrastructure"
    called = [call["tool_name"] for call in body["tool_calls"]]
    assert called == ["lookup_account", "recent_tickets", "check_entitlement"]
    # Output tools are an implementation detail of structured output, not lookups
    # the agent chose to make, so none of them may appear in the trace. (A union
    # output type generates one per member, which is why this is a prefix check.)
    assert not any(name.startswith("final_result") for name in called)


async def test_accounts_endpoint_seeds_the_picker(client):  # noqa: F811
    seeds = client.get("/api/triage/accounts").json()
    assert {s["account"]["account_id"] for s in seeds} == {"ACC-1001", "ACC-1002", "ACC-1003"}
    assert all(s["sample_ticket"] for s in seeds)


async def test_identical_ticket_hits_the_cache(client):  # noqa: F811
    payload = {"action": "resolve", "draft_reply": "Settings > Profile.", "confidence": 0.8}
    request = {"account_id": "ACC-1002", "ticket": "Where do I change my email?"}

    with triage_agent.override(model=decision_model(payload)):
        first = client.post("/api/triage/classify", json=request).json()

    # No override the second time: a cache miss would try a real model request,
    # which conftest's ALLOW_MODEL_REQUESTS=False turns into a loud failure.
    second = client.post("/api/triage/classify", json=request).json()
    assert second == first


async def test_test_model_satisfies_the_union_schema():
    """TestModel synthesizes output from the schema alone; if the union were
    mis-specified (e.g. a missing discriminator) this would fail to validate."""
    with triage_agent.override(model=TestModel()):
        result = await triage_agent.run("A ticket", deps=DEPS)

    assert isinstance(result.output, Resolve | Escalate | NeedsInfo)

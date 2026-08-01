"""Code Review Assistant — offline tests.

The claims worth defending: the specialists really are delegated to (not
inlined), their usage really does bill to the caller's budget, and blowing the
budget is reported as a bounded failure rather than a 500.
"""

from __future__ import annotations

import pytest
from pydantic_ai import ModelResponse, ToolCallPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from app.demos.review.agents import (
    REQUEST_LIMIT,
    lead_reviewer_agent,
    security_agent,
    style_agent,
    tests_agent,
)
from app.demos.review.models import SpecialistFindings
from app.demos.review.router import MAX_DIFF_CHARS, RESPONSE_CACHE
from tests.test_main import client  # noqa: F401 - fixture

DIFF = "diff --git a/api/orders.py b/api/orders.py\n+query = 'SELECT * FROM t WHERE x = ' + arg\n"


@pytest.fixture(autouse=True)
def clear_cache():
    RESPONSE_CACHE.clear()
    yield


def specialist_model(comment: dict, summary: str) -> FunctionModel:
    def respond(messages: list, info: AgentInfo) -> ModelResponse:
        return ModelResponse(
            parts=[
                ToolCallPart(
                    tool_name=info.output_tools[0].name,
                    args={"comments": [comment], "summary": summary},
                )
            ]
        )

    return FunctionModel(respond)


STYLE = specialist_model(
    {
        "file": "api/orders.py",
        "line": 30,
        "severity": "minor",
        "category": "style",
        "message": "find_orders duplicates search_orders.",
    },
    "Checked naming and duplication.",
)
SECURITY = specialist_model(
    {
        "file": "api/orders.py",
        "line": 20,
        "severity": "critical",
        "category": "security",
        "message": "SQL built by string concatenation.",
    },
    "Checked for injection.",
)
TESTS = specialist_model(
    {
        "file": "tests/test_orders.py",
        "line": 8,
        "severity": "major",
        "category": "tests",
        "message": "cancel_order's ValueError path is untested.",
    },
    "Checked coverage.",
)


def lead_model(*, consult: list[str], verdict: str = "request_changes") -> FunctionModel:
    """A lead reviewer that consults the named specialists, then consolidates."""
    state = {"consulted": False}

    def respond(messages: list, info: AgentInfo) -> ModelResponse:
        if not state["consulted"]:
            state["consulted"] = True
            return ModelResponse(parts=[ToolCallPart(tool_name=name, args={}) for name in consult])
        # Carry through whatever the specialists actually returned, so the test
        # asserts on delegated output rather than on a hard-coded answer. Each
        # ToolReturnPart's `.content` is the SpecialistFindings instance the
        # delegated sub-agent produced.
        comments = [
            comment.model_dump()
            for message in messages
            for part in message.parts
            if getattr(part, "tool_name", None) in consult
            and isinstance(getattr(part, "content", None), SpecialistFindings)
            for comment in part.content.comments
        ]
        return ModelResponse(
            parts=[
                ToolCallPart(
                    tool_name=info.output_tools[0].name,
                    args={
                        "verdict": verdict,
                        "summary": "Consolidated the specialists' findings.",
                        "comments": comments,
                    },
                )
            ]
        )

    return FunctionModel(respond)


async def test_lead_reviewer_delegates_to_every_specialist(client):  # noqa: F811
    with (
        lead_reviewer_agent.override(
            model=lead_model(consult=["review_style", "review_security", "review_tests"])
        ),
        style_agent.override(model=STYLE),
        security_agent.override(model=SECURITY),
        tests_agent.override(model=TESTS),
    ):
        response = client.post("/api/review/analyze", json={"diff": DIFF})

    assert response.status_code == 200
    body = response.json()
    assert body["verdict"]["verdict"] == "request_changes"
    categories = {c["category"] for c in body["verdict"]["comments"]}
    assert categories == {"style", "security", "tests"}


async def test_delegated_usage_bills_to_the_callers_budget(client):  # noqa: F811
    """`usage=ctx.usage` is what makes this true; without it the sub-agent runs
    would keep separate tallies and the reported count would be the lead's alone."""
    with (
        lead_reviewer_agent.override(
            model=lead_model(consult=["review_style", "review_security", "review_tests"])
        ),
        style_agent.override(model=STYLE),
        security_agent.override(model=SECURITY),
        tests_agent.override(model=TESTS),
    ):
        body = client.post("/api/review/analyze", json={"diff": DIFF}).json()

    usage = body["usage"]
    # Two lead turns plus one per delegated specialist.
    assert usage["requests"] == 5
    assert usage["request_limit"] == REQUEST_LIMIT
    assert usage["input_tokens"] > 0
    assert usage["output_tokens"] > 0


async def test_the_lead_may_skip_specialists_it_judges_irrelevant(client):  # noqa: F811
    """Which specialists run is the model's call — that's the whole difference
    between this and the graph-driven fan-out in Research Analyst."""
    with (
        lead_reviewer_agent.override(model=lead_model(consult=["review_security"])),
        style_agent.override(model=STYLE),
        security_agent.override(model=SECURITY),
        tests_agent.override(model=TESTS),
    ):
        body = client.post("/api/review/analyze", json={"diff": DIFF}).json()

    assert {c["category"] for c in body["verdict"]["comments"]} == {"security"}
    assert body["usage"]["requests"] == 3


async def test_exceeding_the_request_budget_is_a_clean_422_not_a_500(client):  # noqa: F811
    """A lead reviewer that never stops consulting must hit the ceiling."""

    def never_finishes(messages: list, info: AgentInfo) -> ModelResponse:
        return ModelResponse(parts=[ToolCallPart(tool_name="review_style", args={})])

    with (
        lead_reviewer_agent.override(model=FunctionModel(never_finishes)),
        style_agent.override(model=STYLE),
    ):
        response = client.post("/api/review/analyze", json={"diff": DIFF})

    assert response.status_code == 422
    assert str(REQUEST_LIMIT) in response.json()["detail"]


async def test_empty_diff_is_rejected(client):  # noqa: F811
    assert client.post("/api/review/analyze", json={"diff": "   "}).status_code == 400


async def test_oversized_diff_is_rejected(client):  # noqa: F811
    response = client.post("/api/review/analyze", json={"diff": "x" * (MAX_DIFF_CHARS + 1)})
    assert response.status_code == 413


async def test_sample_diff_is_served_and_plants_all_three_findings(client):  # noqa: F811
    diff = client.get("/api/review/sample-diff").json()["diff"]
    assert "customer_email" in diff  # the string-concatenated SQL (security)
    assert "find_orders" in diff  # the duplicated helper (style)
    assert "cancel_order" in diff  # new behavior whose error path is untested
    assert len(diff) < MAX_DIFF_CHARS


async def test_identical_diff_hits_the_cache(client):  # noqa: F811
    with (
        lead_reviewer_agent.override(model=lead_model(consult=["review_security"])),
        security_agent.override(model=SECURITY),
    ):
        first = client.post("/api/review/analyze", json={"diff": DIFF}).json()

    # No override: a cache miss would attempt a real request, which
    # ALLOW_MODEL_REQUESTS=False turns into a loud failure.
    second = client.post("/api/review/analyze", json={"diff": DIFF}).json()
    assert second == first

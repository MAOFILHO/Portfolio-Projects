import json
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from pydantic_ai.models.test import TestModel

from app.auth import DEMO_PASSWORD, DEMO_USERNAME
from app.demos import DEMOS
from app.demos.research.agents import (
    evaluator_agent,
    planner_agent,
    research_agent,
    synthesizer_agent,
)
from app.demos.research.router import REPORT_CACHE, REVIEW_DEPS, REVIEWS
from app.main import app


@pytest.fixture(autouse=True)
def clear_module_state():
    """Module-level stores would otherwise leak state (and cache hits) between tests."""
    REPORT_CACHE.clear()
    REVIEWS.clear()
    REVIEW_DEPS.clear()
    yield


@pytest.fixture
def client() -> Iterator[TestClient]:
    """A signed-in client. Every demo endpoint is behind the session gate, so
    tests that skip the login step are testing the gate, not the demo."""
    with TestClient(app) as test_client:
        response = test_client.post(
            "/api/login", json={"username": DEMO_USERNAME, "password": DEMO_PASSWORD}
        )
        assert response.status_code == 200, response.text
        yield test_client


@pytest.fixture
def offline_research_agents():
    with (
        planner_agent.override(model=TestModel()),
        research_agent.override(model=TestModel(), native_tools=[]),
        synthesizer_agent.override(model=TestModel()),
        evaluator_agent.override(model=TestModel()),
    ):
        yield


def parse_sse_events(response) -> list[dict]:
    return [json.loads(block[len("data: ") :]) for block in response.text.strip().split("\n\n")]


def research_record(response) -> dict:
    events = parse_sse_events(response)
    assert any(e["type"] == "progress" for e in events), "expected at least one progress event"
    done_events = [e for e in events if e["type"] == "done"]
    assert done_events, f"no 'done' event in stream: {events}"
    return done_events[0]["record"]


def test_health():
    with TestClient(app) as anonymous:
        assert anonymous.get("/health").json() == {"status": "ok"}


# --- the shell and its sign-in gate ----------------------------------------


def test_demos_are_listed_and_mounted(client: TestClient):
    listed = client.get("/api/demos").json()
    assert [d["id"] for d in listed] == [demo.id for demo in DEMOS]
    for entry in listed:
        assert entry["title"] and entry["mechanism"] and entry["blurb"]

    paths = client.get("/openapi.json").json()["paths"]
    for demo in DEMOS:
        assert any(path.startswith(f"/api/{demo.id}/") for path in paths), demo.id


def test_demo_endpoints_require_a_session():
    """The ALB is public and every demo endpoint spends money on model calls,
    so an unauthenticated request must never reach one."""
    with TestClient(app) as anonymous:
        assert anonymous.get("/api/demos").status_code == 401
        assert anonymous.post("/api/research/research", json={"question": "hi"}).status_code == 401
        assert anonymous.get("/api/session").json() == {"username": None}


def test_login_rejects_a_bad_password():
    with TestClient(app) as anonymous:
        response = anonymous.post(
            "/api/login", json={"username": DEMO_USERNAME, "password": "wrong"}
        )
        assert response.status_code == 401
        assert anonymous.get("/api/demos").status_code == 401


def test_session_survives_login_and_ends_at_logout(client: TestClient):
    assert client.get("/api/session").json() == {"username": DEMO_USERNAME}
    client.post("/api/logout")
    assert client.get("/api/session").json() == {"username": None}
    assert client.get("/api/demos").status_code == 401


def test_tampered_session_cookie_is_rejected(client: TestClient):
    payload, _, _signature = client.cookies["showcase_session"].rpartition(".")
    client.cookies.set("showcase_session", f"{payload}.forged-signature")
    assert client.get("/api/demos").status_code == 401


# --- the Research Analyst demo ---------------------------------------------


def test_research_then_approve_flow(client: TestClient, offline_research_agents):
    response = client.post("/api/research/research", json={"question": "SQL vs NoSQL?"})
    assert response.status_code == 200
    record = research_record(response)
    assert record["status"] == "pending_review"

    decision_response = client.post(
        f"/api/research/reviews/{record['review_id']}/decision", json={"decision": "approve"}
    )

    assert decision_response.status_code == 200
    final = decision_response.json()
    assert final["status"] == "final"
    assert final["final"] == final["draft"]


def test_approve_ignores_stray_notes(client: TestClient, offline_research_agents):
    """A client sending notes alongside decision=approve must not have them applied or stored.

    Regression test: the UI used to populate the notes textarea into every decision
    request regardless of which button was clicked, so approving with leftover notes
    silently displayed them as "officer notes" even though nothing was regenerated.
    """
    record = research_record(
        client.post("/api/research/research", json={"question": "SQL vs NoSQL?"})
    )

    final = client.post(
        f"/api/research/reviews/{record['review_id']}/decision",
        json={"decision": "approve", "notes": "these should be ignored"},
    ).json()

    assert final["status"] == "final"
    assert final["final"] == final["draft"]
    assert final["officer_notes"] is None


def test_research_then_annotate_flow(client: TestClient, offline_research_agents):
    record = research_record(
        client.post("/api/research/research", json={"question": "SQL vs NoSQL?"})
    )

    decision_response = client.post(
        f"/api/research/reviews/{record['review_id']}/decision",
        json={"decision": "annotate", "notes": "Add a note about migration cost."},
    )

    assert decision_response.status_code == 200
    final = decision_response.json()
    assert final["status"] == "final"
    assert final["officer_notes"] == "Add a note about migration cost."


def test_annotate_without_notes_is_rejected(client: TestClient, offline_research_agents):
    record = research_record(
        client.post("/api/research/research", json={"question": "SQL vs NoSQL?"})
    )

    decision_response = client.post(
        f"/api/research/reviews/{record['review_id']}/decision", json={"decision": "annotate"}
    )

    assert decision_response.status_code == 400


def test_research_stream_reports_progress_for_each_agent(
    client: TestClient, offline_research_agents
):
    response = client.post("/api/research/research", json={"question": "SQL vs NoSQL?"})

    events = parse_sse_events(response)
    progress_messages = " ".join(e["message"] for e in events if e["type"] == "progress")
    assert "Orchestrator" in progress_messages
    assert "Research" in progress_messages
    assert "Synthesizer" in progress_messages
    assert "Evaluator" in progress_messages


def test_identical_question_hits_the_cache_and_skips_the_pipeline(
    client: TestClient, offline_research_agents
):
    first = client.post("/api/research/research", json={"question": "What is edge computing?"})
    first_record = research_record(first)

    # Same question, different casing/whitespace - should still be a cache hit.
    second = client.post("/api/research/research", json={"question": "  What IS edge computing?  "})
    second_events = parse_sse_events(second)
    second_record = research_record(second)

    progress_messages = " ".join(e["message"] for e in second_events if e["type"] == "progress")
    assert "cached" in progress_messages.lower()
    assert "Orchestrator" not in progress_messages
    assert second_record["draft"] == first_record["draft"]
    assert second_record["review_id"] != first_record["review_id"]

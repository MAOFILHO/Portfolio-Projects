from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.deps import get_query_agent
from app.routes import query


class _FakeQueryAgent:
    def __init__(self, answer: str) -> None:
        self._answer = answer
        self.last_question: str | None = None

    async def answer(self, question: str) -> str:
        self.last_question = question
        return self._answer


def _make_client(fake_agent: _FakeQueryAgent) -> TestClient:
    app = FastAPI()
    app.include_router(query.router)
    app.dependency_overrides[get_query_agent] = lambda: fake_agent
    return TestClient(app)


def test_query_route_returns_agent_answer():
    fake_agent = _FakeQueryAgent("Nobody was detected at the driveway camera between 2pm and 3pm yesterday.")
    client = _make_client(fake_agent)

    response = client.post("/api/v1/query", json={"question": "Was anyone at the driveway yesterday afternoon?"})

    assert response.status_code == 200
    assert response.json() == {"answer": "Nobody was detected at the driveway camera between 2pm and 3pm yesterday."}
    assert fake_agent.last_question == "Was anyone at the driveway yesterday afternoon?"

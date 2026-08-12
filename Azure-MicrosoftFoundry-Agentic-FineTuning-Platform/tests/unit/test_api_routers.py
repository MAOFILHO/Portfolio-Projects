"""API-level tests via FastAPI's TestClient — no network, no live Azure."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


def test_health(client: TestClient):
    res = client.get("/health")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ok"
    assert body["demo_mode"] == "mock"
    assert body["region"] == "eastus2"


def test_mcp_tools_lists_19_tools(client: TestClient):
    res = client.get("/mcp/tools")
    assert res.status_code == 200
    assert res.json()["count"] == 19


def test_login_success(client: TestClient):
    res = client.post("/auth/login", json={"username": "demo", "password": "demo123"})
    assert res.status_code == 200
    body = res.json()
    assert body["authenticated"] is True
    assert "not real authentication" in body["notice"].lower()


def test_login_failure(client: TestClient):
    res = client.post("/auth/login", json={"username": "demo", "password": "wrong"})
    assert res.status_code == 401


def test_leaderboard_quality_index(client: TestClient):
    res = client.get("/catalog/leaderboard", params={"metric": "quality_index"})
    assert res.status_code == 200
    assert res.json()["better"] == "higher"


def test_finetune_validate(client: TestClient):
    res = client.get("/finetune/validate")
    assert res.status_code == 200
    body = res.json()
    assert body["valid_rows"] == 10
    assert body["total_lines"] == 10


def test_finetune_upload_invalid_file_returns_200_with_data(client: TestClient):
    # Schema violations are data, not an HTTP error — the UI renders them as a
    # demonstrated feature per the skill's standing rule.
    bad_jsonl = b'{"messages": [{"role": "user", "content": "only one message"}]}\n'
    res = client.post(
        "/finetune/validate/upload",
        files={"file": ("bad.jsonl", bad_jsonl, "application/octet-stream")},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["is_valid"] is False
    assert len(body["errors"]) == 1


def test_inference_canonical_prompts(client: TestClient):
    res = client.get("/inference/prompts")
    assert res.status_code == 200
    body = res.json()
    assert len(body["prompts"]) == 5
    assert "travel assistant" in body["system_prompt"].lower()


def test_agent_invoke_requires_request_or_demo(client: TestClient):
    res = client.post("/agent/invoke", json={})
    assert res.status_code == 422


def test_agent_invoke_demo_discovery(client: TestClient):
    res = client.post("/agent/invoke", json={"demo": "discovery"})
    assert res.status_code == 200
    body = res.json()
    assert body["demo"] == "discovery"
    assert "error" not in body or body.get("error") is None


def test_agent_route_dry_run(client: TestClient):
    res = client.post("/agent/route", json={"request": "run the leaderboard comparison"})
    assert res.status_code == 200
    assert res.json()["demo"] in {"discovery", "finetune", "comparison"}

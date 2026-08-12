"""Additional API-level tests covering endpoints not exercised in
test_api_routers.py (catalog model detail, compare, evaluate; finetune job
lifecycle; inference chat/compare)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


def test_catalog_models_list(client: TestClient):
    res = client.get("/catalog/models")
    assert res.status_code == 200
    assert len(res.json()) >= 1


def test_catalog_model_card_by_name(client: TestClient):
    res = client.get("/catalog/models/gpt-5.4")
    assert res.status_code == 200
    assert res.json()["name"] == "gpt-5.4"


def test_catalog_model_card_unknown_404s(client: TestClient):
    res = client.get("/catalog/models/not-a-real-model")
    assert res.status_code == 404


def test_catalog_benchmarks(client: TestClient):
    res = client.get("/catalog/benchmarks/gpt-5.4")
    assert res.status_code == 200


def test_catalog_leaderboard_all_axes(client: TestClient):
    res = client.get("/catalog/leaderboard/all")
    assert res.status_code == 200
    body = res.json()
    assert set(body.keys()) >= {
        "quality_index",
        "safety_attack_success_rate",
        "throughput_tps",
        "benchmark_cost_usd",
    }


def test_catalog_compare(client: TestClient):
    res = client.get("/catalog/compare")
    assert res.status_code == 200


def test_catalog_evaluate_and_fetch_results(client: TestClient):
    res = client.post("/catalog/evaluate", json={})
    assert res.status_code == 200
    res2 = client.get("/catalog/evaluate/results")
    assert res2.status_code == 200
    assert "704" in res2.json()["overall_score"]


def test_catalog_dataset_synthetic(client: TestClient):
    res = client.get("/catalog/dataset/synthetic")
    assert res.status_code == 200


def test_finetune_estimate(client: TestClient):
    res = client.post(
        "/finetune/estimate",
        json={"billed_tokens": 16000, "epochs": 2, "training_type": "Developer"},
    )
    assert res.status_code == 200
    assert res.json()["estimated_usd"] == pytest.approx(0.016, abs=0.001)


def test_finetune_full_job_lifecycle(client: TestClient):
    create = client.post("/finetune/jobs", json={})
    assert create.status_code == 200
    job_id = create.json()["job_id"]

    status = client.get(f"/finetune/jobs/{job_id}")
    assert status.status_code == 200
    assert status.json()["status"] in {"queued", "running", "succeeded"}

    logs = client.get(f"/finetune/jobs/{job_id}/logs")
    assert logs.status_code == 200

    checkpoints = client.get(f"/finetune/jobs/{job_id}/checkpoints")
    assert checkpoints.status_code == 200

    deploy = client.post("/finetune/deploy", json={})
    assert deploy.status_code == 200
    assert deploy.json()["deployment_type"] == "Developer"


def test_inference_chat(client: TestClient):
    res = client.post(
        "/inference/chat", json={"prompt": "Where should I go in Rome?", "fine_tuned": False}
    )
    assert res.status_code == 200
    assert res.json()["response"]


def test_inference_compare_uses_canonical_prompts_by_default(client: TestClient):
    res = client.post("/inference/compare", json={})
    assert res.status_code == 200
    body = res.json()
    assert len(body["comparisons"]) == 5

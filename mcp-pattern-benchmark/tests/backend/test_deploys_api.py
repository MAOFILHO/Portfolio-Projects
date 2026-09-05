"""Tests for the /deploys HTTP API.

Same seam as test_runbooks_api.py: a real HTTP-shaped test client, backed by
a real (throwaway) Postgres.
"""

from fastapi.testclient import TestClient

from backend.app import app
from backend.seed import reset_and_seed


def test_create_deploy_persists_a_pending_deploy(db):
    reset_and_seed(db)
    client = TestClient(app)

    response = client.post("/deploys", json={"repo_id": 1, "environment": "production"})

    assert response.status_code == 200
    deploy = response.json()
    assert deploy["repo_id"] == 1
    assert deploy["environment"] == "production"
    assert deploy["status"] == "pending"


def test_get_deploy_returns_the_matching_deploy(db):
    reset_and_seed(db)
    client = TestClient(app)
    created = client.post("/deploys", json={"repo_id": 1, "environment": "production"}).json()

    response = client.get(f"/deploys/{created['id']}")

    assert response.status_code == 200
    assert response.json() == created


def test_get_deploy_404s_for_an_unknown_id(db):
    reset_and_seed(db)
    client = TestClient(app)

    response = client.get("/deploys/999")

    assert response.status_code == 404


def test_update_deploy_status(db):
    reset_and_seed(db)
    client = TestClient(app)
    created = client.post("/deploys", json={"repo_id": 1, "environment": "production"}).json()

    response = client.patch(f"/deploys/{created['id']}", json={"status": "succeeded"})

    assert response.status_code == 200
    assert response.json()["status"] == "succeeded"


def test_update_deploy_status_404s_for_an_unknown_id(db):
    reset_and_seed(db)
    client = TestClient(app)

    response = client.patch("/deploys/999", json={"status": "succeeded"})

    assert response.status_code == 404

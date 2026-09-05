"""Tests for the /runbooks HTTP API.

Same seam as test_change_requests_api.py: a real HTTP-shaped test client,
backed by a real (throwaway) Postgres.
"""

from fastapi.testclient import TestClient

from backend.app import app
from backend.seed import reset_and_seed


def test_list_runbooks_returns_the_seeded_runbooks_for_a_repo(db):
    reset_and_seed(db)
    client = TestClient(app)

    response = client.get("/runbooks", params={"repo_id": 1})

    assert response.status_code == 200
    runbooks = response.json()
    assert len(runbooks) >= 1
    assert runbooks[0]["repo_id"] == 1
    assert runbooks[0]["internal_notes"] != ""


def test_get_runbook_returns_the_matching_runbook(db):
    reset_and_seed(db)
    client = TestClient(app)

    response = client.get("/runbooks/1")

    assert response.status_code == 200
    runbook = response.json()
    assert runbook["id"] == 1
    assert runbook["title"] == "Rolling back a bad billing deploy"
    assert runbook["internal_notes"] == (
        "Escalate to payments-oncall before rolling back; "
        "past rollbacks corrupted the ledger."
    )


def test_get_runbook_404s_for_an_unknown_id(db):
    reset_and_seed(db)
    client = TestClient(app)

    response = client.get("/runbooks/999")

    assert response.status_code == 404

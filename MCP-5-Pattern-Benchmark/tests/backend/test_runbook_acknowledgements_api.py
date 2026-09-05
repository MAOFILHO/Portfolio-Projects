"""Tests for the /runbooks acknowledgements HTTP API.

Same seam as test_change_requests_api.py's review_comments tests: a real
HTTP-shaped test client, backed by a real (throwaway) Postgres.
"""

from fastapi.testclient import TestClient

from backend.app import app
from backend.seed import reset_and_seed


def test_add_runbook_acknowledgement_persists_a_note(db):
    reset_and_seed(db)
    client = TestClient(app)

    response = client.post("/runbooks/1/acknowledgements", json={"note": "Reviewed, will follow"})

    assert response.status_code == 200
    ack = response.json()
    assert ack["runbook_id"] == 1
    assert ack["note"] == "Reviewed, will follow"
    assert client.get("/runbooks/1/acknowledgements").json() == [ack]


def test_list_runbook_acknowledgements_returns_only_the_matching_runbooks_notes(db):
    reset_and_seed(db)
    client = TestClient(app)
    client.post("/runbooks/1/acknowledgements", json={"note": "For runbook 1"})
    client.post("/runbooks/2/acknowledgements", json={"note": "For runbook 2"})

    response = client.get("/runbooks/1/acknowledgements")

    assert response.status_code == 200
    notes = response.json()
    assert [n["note"] for n in notes] == ["For runbook 1"]

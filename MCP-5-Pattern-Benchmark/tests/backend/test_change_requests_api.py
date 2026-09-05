"""Tests for the /repos change-request HTTP API.

Same seam as test_tickets_api.py: a real HTTP-shaped test client, backed by
a real (throwaway) Postgres.
"""

from fastapi.testclient import TestClient

from backend.app import app
from backend.seed import reset_and_seed


def test_list_change_requests_returns_the_seeded_change_requests_for_a_repo(db):
    reset_and_seed(db)
    client = TestClient(app)

    response = client.get("/repos/1/change-requests")

    assert response.status_code == 200
    crs = response.json()
    assert len(crs) >= 1
    assert crs[0]["repo_id"] == 1
    assert crs[0]["status"] == "open"


def test_list_all_change_requests_returns_change_requests_across_every_repo(db):
    reset_and_seed(db)
    client = TestClient(app)

    response = client.get("/change-requests")

    assert response.status_code == 200
    crs = response.json()
    assert len(crs) == 8
    assert {cr["repo_id"] for cr in crs} == {1, 2, 3, 4}


def test_get_change_request_returns_the_matching_change_request(db):
    reset_and_seed(db)
    client = TestClient(app)

    response = client.get("/change-requests/1")

    assert response.status_code == 200
    cr = response.json()
    assert cr["id"] == 1
    assert cr["title"] == "Fix rounding error in invoice totals"
    assert cr["status"] == "open"


def test_get_change_request_404s_for_an_unknown_id(db):
    reset_and_seed(db)
    client = TestClient(app)

    response = client.get("/change-requests/999")

    assert response.status_code == 404


def test_add_review_comment_persists_a_comment(db):
    reset_and_seed(db)
    client = TestClient(app)

    response = client.post("/change-requests/1/comments", json={"body": "Off by one here"})

    assert response.status_code == 200
    comment = response.json()
    assert comment["change_request_id"] == 1
    assert comment["body"] == "Off by one here"
    assert client.get("/change-requests/1/comments").json() == [comment]


def test_update_change_request_status(db):
    reset_and_seed(db)
    client = TestClient(app)

    response = client.patch("/change-requests/1", json={"status": "approved"})

    assert response.status_code == 200
    assert response.json()["status"] == "approved"


def test_update_change_request_status_404s_for_an_unknown_id(db):
    reset_and_seed(db)
    client = TestClient(app)

    response = client.patch("/change-requests/999", json={"status": "approved"})

    assert response.status_code == 404

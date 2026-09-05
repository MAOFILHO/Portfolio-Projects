"""Tests for the /tickets HTTP API.

Drives the FastAPI app through a real HTTP-shaped test client, backed by a
real (throwaway) Postgres, exactly the interface server_wrapper calls.
"""

from fastapi.testclient import TestClient

from backend.app import app


def test_list_tickets_returns_empty_list_on_fresh_schema(db):
    client = TestClient(app)

    response = client.get("/tickets")

    assert response.status_code == 200
    assert response.json() == []


def test_create_ticket_makes_it_show_up_in_the_list(db):
    client = TestClient(app)

    created = client.post("/tickets", json={"title": "Printer offline", "description": "n/a"})
    ticket = created.json()

    assert created.status_code == 200
    assert isinstance(ticket["id"], int)
    assert ticket["title"] == "Printer offline"
    assert ticket["status"] == "open"
    assert ticket["assignee"] is None
    assert client.get("/tickets").json() == [ticket]


def test_get_ticket_returns_the_matching_ticket(db):
    client = TestClient(app)
    created = client.post("/tickets", json={"title": "Printer offline"}).json()

    response = client.get(f"/tickets/{created['id']}")

    assert response.status_code == 200
    assert response.json() == created


def test_get_ticket_404s_for_an_unknown_id(db):
    client = TestClient(app)

    response = client.get("/tickets/999")

    assert response.status_code == 404


def test_update_ticket_applies_status_and_assignee(db):
    client = TestClient(app)
    created = client.post("/tickets", json={"title": "Printer offline"}).json()

    response = client.patch(f"/tickets/{created['id']}", json={"status": "closed", "assignee": "asmith"})

    assert response.status_code == 200
    assert response.json() == {**created, "status": "closed", "assignee": "asmith"}


def test_update_ticket_leaves_unset_fields_unchanged(db):
    client = TestClient(app)
    created = client.post("/tickets", json={"title": "Printer offline"}).json()
    client.patch(f"/tickets/{created['id']}", json={"assignee": "asmith"})

    response = client.patch(f"/tickets/{created['id']}", json={"status": "closed"})

    assert response.json() == {**created, "status": "closed", "assignee": "asmith"}


def test_update_ticket_404s_for_an_unknown_id(db):
    client = TestClient(app)

    response = client.patch("/tickets/999", json={"status": "closed"})

    assert response.status_code == 404


def test_add_comment_returns_the_created_comment(db):
    client = TestClient(app)
    created = client.post("/tickets", json={"title": "Printer offline"}).json()

    response = client.post(f"/tickets/{created['id']}/comments", json={"body": "Looking into it"})

    assert response.status_code == 200
    comment = response.json()
    assert isinstance(comment["id"], int)
    assert comment["ticket_id"] == created["id"]
    assert comment["body"] == "Looking into it"


def test_add_attachment_returns_the_created_attachment(db):
    client = TestClient(app)
    created = client.post("/tickets", json={"title": "Printer offline"}).json()

    response = client.post(f"/tickets/{created['id']}/attachments", json={"filename": "screenshot.png"})

    assert response.status_code == 200
    attachment = response.json()
    assert isinstance(attachment["id"], int)
    assert attachment["ticket_id"] == created["id"]
    assert attachment["filename"] == "screenshot.png"

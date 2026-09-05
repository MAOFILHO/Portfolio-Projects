"""Tests for the customer lookup added to the /tickets namespace (Phase 2:
Domain-Specific Adapter).

Drives the same FastAPI app as test_tickets_api.py through a real HTTP-shaped
test client, backed by a real (throwaway) Postgres.
"""

import psycopg2
from fastapi.testclient import TestClient

from backend.app import app


def _insert_customer(db: str, name: str, tier: str) -> int:
    conn = psycopg2.connect(db)
    try:
        with conn, conn.cursor() as cur:
            cur.execute(
                "INSERT INTO customers (name, tier) VALUES (%s, %s) RETURNING id", (name, tier)
            )
            return cur.fetchone()[0]
    finally:
        conn.close()


def test_get_ticket_customer_returns_the_linked_customer(db):
    client = TestClient(app)
    customer_id = _insert_customer(db, "Acme Corp", "premium")
    ticket = client.post(
        "/tickets", json={"title": "Printer offline", "customer_id": customer_id}
    ).json()

    response = client.get(f"/tickets/{ticket['id']}/customer")

    assert response.status_code == 200
    assert response.json() == {"id": customer_id, "name": "Acme Corp", "tier": "premium"}


def test_get_ticket_customer_404s_for_an_unknown_ticket(db):
    client = TestClient(app)

    response = client.get("/tickets/999/customer")

    assert response.status_code == 404


def test_get_ticket_customer_404s_when_the_ticket_has_no_customer(db):
    client = TestClient(app)
    ticket = client.post("/tickets", json={"title": "Printer offline"}).json()

    response = client.get(f"/tickets/{ticket['id']}/customer")

    assert response.status_code == 404

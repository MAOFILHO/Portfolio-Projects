"""Tests for the seed script: resets and reloads the schema, then loads the
fixed initial state every task run starts from.

Verifies through the HTTP API (the public interface), not by querying
Postgres directly.
"""

from fastapi.testclient import TestClient

from backend.app import app
from backend.seed import reset_and_seed


def test_reset_and_seed_loads_the_fixed_initial_tickets(db):
    reset_and_seed(db)
    client = TestClient(app)

    response = client.get("/tickets")

    assert response.json() == [
        {"id": 1, "title": "Printer not connecting to network", "status": "open", "assignee": None},
        {"id": 2, "title": "Password reset request", "status": "closed", "assignee": "jdoe"},
        {"id": 3, "title": "VPN access failing for remote team", "status": "open", "assignee": None},
        {"id": 4, "title": "Invoice not received for last billing cycle", "status": "open", "assignee": None},
        {"id": 5, "title": "Security camera feed offline at HQ", "status": "open", "assignee": None},
        {"id": 6, "title": "Loyalty points not applied at checkout", "status": "open", "assignee": None},
        {"id": 7, "title": "API rate limit errors on integration", "status": "open", "assignee": None},
        {"id": 8, "title": "Shipping label printer jammed", "status": "open", "assignee": None},
    ]


def test_reset_and_seed_links_customers_to_the_fixed_tickets(db):
    reset_and_seed(db)
    client = TestClient(app)

    assert client.get("/tickets/1/customer").json() == {
        "id": 1, "name": "Acme Corp", "tier": "premium",
    }
    assert client.get("/tickets/2/customer").json() == {
        "id": 2, "name": "Bob's Shop", "tier": "standard",
    }

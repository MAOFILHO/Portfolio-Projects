"""Seed data standing in for the CRM a real deployment would query.

Chosen so the demo reliably exercises all three union branches: Northwind is a
high-spend enterprise account mid-incident (escalation bait), Fabrikam is a
free-plan account with a simple how-to question (resolvable), and Adventure
Works has a history of vague reports (usually needs more information).
"""

from __future__ import annotations

from .models import Account, PastTicket

ACCOUNTS: dict[str, Account] = {
    "ACC-1001": Account(
        account_id="ACC-1001",
        company="Northwind Traders",
        plan="enterprise",
        seats=2400,
        monthly_spend_usd=48000,
        support_sla_hours=1,
        open_incidents=2,
    ),
    "ACC-1002": Account(
        account_id="ACC-1002",
        company="Fabrikam Inc.",
        plan="free",
        seats=3,
        monthly_spend_usd=0,
        support_sla_hours=72,
    ),
    "ACC-1003": Account(
        account_id="ACC-1003",
        company="Adventure Works",
        plan="business",
        seats=45,
        monthly_spend_usd=1350,
        support_sla_hours=8,
    ),
}

TICKETS: dict[str, list[PastTicket]] = {
    "ACC-1001": [
        PastTicket(
            ticket_id="T-8817", subject="Region failover took 40 minutes", resolved=True, days_ago=6
        ),
        PastTicket(
            ticket_id="T-8901", subject="Elevated 5xx on the ingest API", resolved=False, days_ago=1
        ),
    ],
    "ACC-1002": [
        PastTicket(
            ticket_id="T-8420", subject="How do I invite a teammate?", resolved=True, days_ago=30
        ),
    ],
    "ACC-1003": [
        PastTicket(
            ticket_id="T-8666", subject="Dashboard looks wrong", resolved=False, days_ago=12
        ),
        PastTicket(ticket_id="T-8702", subject="Export is broken", resolved=False, days_ago=4),
    ],
}

SAMPLE_TICKETS: dict[str, str] = {
    "ACC-1001": (
        "Our production ingest pipeline has been returning 503s for the last 25 minutes "
        "across eu-west-1. We have customers reporting data loss. This is business-critical."
    ),
    "ACC-1002": (
        "Hi, where do I change the email address on my account? I looked in Settings "
        "but couldn't find it."
    ),
    "ACC-1003": (
        "Something is off with the numbers again. Can you take a look? It's not matching "
        "what we expect."
    ),
}

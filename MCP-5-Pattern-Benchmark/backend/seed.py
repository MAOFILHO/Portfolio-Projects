"""Seed script for the /tickets backend.

Resets and reloads the schema, then loads the fixed initial state every task
run starts from. Run as a script (uses DATABASE_URL) or imported by the
harness's state manager before each task.
"""

import os
from pathlib import Path

import psycopg2

SCHEMA_PATH = Path(__file__).parent / "schema.sql"

INITIAL_CUSTOMERS = [
    ("Acme Corp", "premium"),
    ("Bob's Shop", "standard"),
    ("Globex Industries", "premium"),
    ("Initech", "standard"),
    ("Wayne Enterprises", "premium"),
    ("Stark Retail", "standard"),
    ("Umbrella Labs", "premium"),
    ("Wonka Supplies", "standard"),
]

# customer index (0-based, into INITIAL_CUSTOMERS) or None
INITIAL_TICKETS = [
    ("Printer not connecting to network", "", "open", None, 0),
    ("Password reset request", "", "closed", "jdoe", 1),
    ("VPN access failing for remote team", "", "open", None, 2),
    ("Invoice not received for last billing cycle", "", "open", None, 3),
    ("Security camera feed offline at HQ", "", "open", None, 4),
    ("Loyalty points not applied at checkout", "", "open", None, 5),
    ("API rate limit errors on integration", "", "open", None, 6),
    ("Shipping label printer jammed", "", "open", None, 7),
]

INITIAL_REPOS = ["billing-service", "checkout-web", "auth-service", "notifications-service"]

# repo index (0-based, into INITIAL_REPOS)
INITIAL_CHANGE_REQUESTS = [
    ("Fix rounding error in invoice totals", "--- a/invoice.py\n+++ b/invoice.py\n", 0),
    ("Add retry to payment webhook", "--- a/webhook.py\n+++ b/webhook.py\n", 0),
    ("Speed up cart page load", "--- a/cart.tsx\n+++ b/cart.tsx\n", 1),
    ("Cache product search results", "--- a/search.tsx\n+++ b/search.tsx\n", 1),
    ("Fix auth token expiry check", "--- a/tokens.py\n+++ b/tokens.py\n", 2),
    ("Add rate limiting to login endpoint", "--- a/login.py\n+++ b/login.py\n", 2),
    ("Batch email notifications", "--- a/email.py\n+++ b/email.py\n", 3),
    ("Fix duplicate SMS alerts", "--- a/sms.py\n+++ b/sms.py\n", 3),
]

# repo index (0-based, into INITIAL_REPOS). internal_notes is withheld from
# any customer-safe surface (Phase 5) -- never present in a runbook resource
# or acknowledgement, only in the control's flat tool response.
INITIAL_RUNBOOKS = [
    (
        "Rolling back a bad billing deploy",
        "1. Halt traffic. 2. Redeploy last tag.",
        "Escalate to payments-oncall before rolling back; past rollbacks corrupted the ledger.",
        0,
    ),
    (
        "Reconciling a stuck payment webhook",
        "1. Check dead-letter queue. 2. Replay.",
        "The vendor sandbox key is hardcoded in webhook.py; rotate it after use.",
        0,
    ),
    (
        "Clearing the checkout cache",
        "1. Flush cache. 2. Warm top 100 SKUs.",
        "The cache-warm script has caused an OOM twice; run it during low traffic only.",
        1,
    ),
    (
        "Handling a cart-service outage",
        "1. Fail over to read replica.",
        "The failover replica is two releases behind; verify schema compatibility first.",
        1,
    ),
    (
        "Rotating an expired auth signing key",
        "1. Generate new key. 2. Dual-publish.",
        "The backup signing key is stored in the ops vault under 'auth-key-backup'.",
        2,
    ),
    (
        "Responding to a login brute-force spike",
        "1. Enable rate limit. 2. Block IPs.",
        "IP blocklist changes need security team sign-off before deploy.",
        2,
    ),
    (
        "Draining the notification queue",
        "1. Pause producers. 2. Drain workers.",
        "Some queued messages carry unredacted customer emails; never log them.",
        3,
    ),
    (
        "Recovering from an SMS provider outage",
        "1. Switch provider. 2. Resend failed.",
        "The backup SMS provider bills 10x the normal rate; get finance approval first.",
        3,
    ),
]


def reset_and_seed(database_url: str) -> None:
    conn = psycopg2.connect(database_url)
    try:
        with conn, conn.cursor() as cur:
            cur.execute(SCHEMA_PATH.read_text())
            customer_ids = []
            for name, tier in INITIAL_CUSTOMERS:
                cur.execute(
                    "INSERT INTO customers (name, tier) VALUES (%s, %s) RETURNING id",
                    (name, tier),
                )
                customer_ids.append(cur.fetchone()[0])
            for title, description, status, assignee, customer_index in INITIAL_TICKETS:
                customer_id = (
                    customer_ids[customer_index] if customer_index is not None else None
                )
                cur.execute(
                    "INSERT INTO tickets (title, description, status, assignee, customer_id) "
                    "VALUES (%s, %s, %s, %s, %s)",
                    (title, description, status, assignee, customer_id),
                )
            repo_ids = []
            for name in INITIAL_REPOS:
                cur.execute("INSERT INTO repos (name) VALUES (%s) RETURNING id", (name,))
                repo_ids.append(cur.fetchone()[0])
            for title, diff, repo_index in INITIAL_CHANGE_REQUESTS:
                cur.execute(
                    "INSERT INTO change_requests (repo_id, title, diff) VALUES (%s, %s, %s)",
                    (repo_ids[repo_index], title, diff),
                )
            for title, body, internal_notes, repo_index in INITIAL_RUNBOOKS:
                cur.execute(
                    "INSERT INTO runbooks (repo_id, title, body, internal_notes) "
                    "VALUES (%s, %s, %s, %s)",
                    (repo_ids[repo_index], title, body, internal_notes),
                )
    finally:
        conn.close()


if __name__ == "__main__":
    reset_and_seed(os.environ["DATABASE_URL"])

"""Tests for the eight incident-handling tasks' verify.py scripts.

Each verify.py is run exactly as the harness does: a subprocess reading
DATABASE_URL from the environment (src/base/task_manager.py's default
verification command).
"""

import os
import subprocess
import sys
from pathlib import Path

import psycopg2
import pytest

from backend.seed import reset_and_seed

TASKS_ROOT = Path(__file__).resolve().parent.parent / "tasks/tool_orchestrator/standard/incidents"

# (task_id, title the task asks the agent to use, assignee, evidence filename)
INCIDENTS = [
    ("printer_offline", "Office printer offline in Building 3", "asmith", "printer_photo.jpg"),
    ("vpn_login_failures", "VPN login failures for remote staff", "bchen", "vpn_error_log.txt"),
    ("database_latency_spike", "Database latency spike on orders service", "cwang", "latency_graph.png"),
    ("billing_webhook_failures", "Billing webhook deliveries failing", "dpatel", "webhook_errors.log"),
    ("staging_deploy_broken", "Staging deploy broken after last release", "egarcia", "deploy_output.txt"),
    ("email_delivery_delayed", "Outbound email delivery delayed", "fkim", "mail_queue_report.csv"),
    ("ssl_cert_expiring", "SSL certificate expiring on api.internal", "gnguyen", "cert_details.txt"),
    ("disk_space_critical", "Disk space critical on build server", "hoconnor", "disk_usage.png"),
]


def run_verify(task_id: str, database_url: str) -> subprocess.CompletedProcess:
    verify_path = TASKS_ROOT / task_id / "verify.py"
    return subprocess.run(
        [sys.executable, str(verify_path)],
        capture_output=True,
        text=True,
        env={**os.environ, "DATABASE_URL": database_url},
    )


def _create_incident(database_url, title, assignee, filename, with_comment=True):
    with psycopg2.connect(database_url) as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO tickets (title, assignee) VALUES (%s, %s) RETURNING id", (title, assignee)
        )
        ticket_id = cur.fetchone()[0]
        cur.execute(
            "INSERT INTO attachments (ticket_id, filename) VALUES (%s, %s)", (ticket_id, filename)
        )
        if with_comment:
            cur.execute(
                "INSERT INTO comments (ticket_id, body) VALUES (%s, %s)",
                (ticket_id, f"Assigned to {assignee}"),
            )


@pytest.mark.parametrize("task_id, title, assignee, filename", INCIDENTS)
def test_verify_passes_when_the_incident_was_fully_handled(db, task_id, title, assignee, filename):
    reset_and_seed(db)
    _create_incident(db, title, assignee, filename)

    result = run_verify(task_id, db)

    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("task_id, title, assignee, filename", INCIDENTS)
def test_verify_fails_when_the_ticket_was_never_assigned(db, task_id, title, assignee, filename):
    reset_and_seed(db)
    _create_incident(db, title, None, filename)

    result = run_verify(task_id, db)

    assert result.returncode != 0


@pytest.mark.parametrize("task_id, title, assignee, filename", INCIDENTS)
def test_verify_fails_when_no_evidence_was_attached(db, task_id, title, assignee, filename):
    reset_and_seed(db)
    with psycopg2.connect(db) as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO tickets (title, assignee) VALUES (%s, %s)", (title, assignee)
        )

    result = run_verify(task_id, db)

    assert result.returncode != 0

"""Tests for the eight customer-resolution tasks' verify.py scripts.

Each verify.py is run exactly as the harness does: a subprocess reading
DATABASE_URL from the environment (src/base/task_manager.py's default
verification command). Same shape as test_verify_incidents.py.
"""

import os
import subprocess
import sys
from pathlib import Path

import psycopg2
import pytest

from backend.seed import reset_and_seed

TASKS_ROOT = Path(__file__).resolve().parent.parent / "tasks/domain_adapter/standard/customer_resolutions"

# (task_id, ticket title, expected assignee, tag expected on the note)
RESOLUTIONS = [
    ("acme_printer_fixed", "Printer not connecting to network", "priority-support", True),
    ("bobs_password_reset", "Password reset request", "support-standard", False),
    ("globex_vpn_access", "VPN access failing for remote team", "priority-support", True),
    ("initech_invoice_missing", "Invoice not received for last billing cycle", "support-standard", False),
    ("wayne_camera_offline", "Security camera feed offline at HQ", "priority-support", True),
    ("stark_loyalty_points", "Loyalty points not applied at checkout", "support-standard", False),
    ("umbrella_rate_limit", "API rate limit errors on integration", "priority-support", True),
    ("wonka_printer_jam", "Shipping label printer jammed", "support-standard", False),
]


def run_verify(task_id: str, database_url: str) -> subprocess.CompletedProcess:
    verify_path = TASKS_ROOT / task_id / "verify.py"
    return subprocess.run(
        [sys.executable, str(verify_path)],
        capture_output=True,
        text=True,
        env={**os.environ, "DATABASE_URL": database_url},
    )


def _resolve_ticket(database_url, title, assignee, tagged):
    note = "[PRIORITY] Fixed" if tagged else "Fixed"
    with psycopg2.connect(database_url) as conn, conn.cursor() as cur:
        cur.execute(
            "UPDATE tickets SET status = 'resolved', assignee = %s WHERE title = %s",
            (assignee, title),
        )
        cur.execute(
            "INSERT INTO comments (ticket_id, body) "
            "SELECT id, %s FROM tickets WHERE title = %s",
            (note, title),
        )


@pytest.mark.parametrize("task_id, title, assignee, tagged", RESOLUTIONS)
def test_verify_passes_when_the_ticket_was_correctly_resolved(db, task_id, title, assignee, tagged):
    reset_and_seed(db)
    _resolve_ticket(db, title, assignee, tagged)

    result = run_verify(task_id, db)

    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("task_id, title, assignee, tagged", RESOLUTIONS)
def test_verify_fails_when_the_ticket_was_never_resolved(db, task_id, title, assignee, tagged):
    reset_and_seed(db)

    result = run_verify(task_id, db)

    assert result.returncode != 0


@pytest.mark.parametrize("task_id, title, assignee, tagged", RESOLUTIONS)
def test_verify_fails_when_routed_to_the_wrong_queue(db, task_id, title, assignee, tagged):
    reset_and_seed(db)
    wrong_assignee = "support-standard" if assignee == "priority-support" else "priority-support"
    _resolve_ticket(db, title, wrong_assignee, tagged)

    result = run_verify(task_id, db)

    assert result.returncode != 0


@pytest.mark.parametrize("task_id, title, assignee, tagged", [r for r in RESOLUTIONS if r[3]])
def test_verify_fails_when_a_premium_note_is_missing_its_tag(db, task_id, title, assignee, tagged):
    reset_and_seed(db)
    _resolve_ticket(db, title, assignee, tagged=False)

    result = run_verify(task_id, db)

    assert result.returncode != 0

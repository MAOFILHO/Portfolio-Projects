"""Tests for the shared Postgres-reading helper every verify.py uses."""

from backend.seed import reset_and_seed
from tasks.utils.backend_state import (
    find_change_request_by_title,
    find_ticket_by_title,
    find_deploy_by_repo_and_environment,
    get_change_request,
    get_deploy,
    get_runbook,
    get_ticket,
    list_attachments,
    list_comments,
    list_review_comments,
    list_runbook_acknowledgements,
)


def test_get_ticket_returns_the_matching_ticket(db):
    reset_and_seed(db)

    ticket = get_ticket(1)

    assert ticket == {
        "id": 1,
        "title": "Printer not connecting to network",
        "status": "open",
        "assignee": None,
    }


def test_get_ticket_returns_none_for_an_unknown_id(db):
    reset_and_seed(db)

    assert get_ticket(999) is None


def test_find_ticket_by_title_returns_the_matching_ticket(db):
    reset_and_seed(db)

    ticket = find_ticket_by_title("Password reset request")

    assert ticket == {
        "id": 2,
        "title": "Password reset request",
        "status": "closed",
        "assignee": "jdoe",
    }


def test_find_ticket_by_title_returns_none_for_an_unknown_title(db):
    reset_and_seed(db)

    assert find_ticket_by_title("no such ticket") is None


def test_list_comments_returns_comments_for_the_ticket(db):
    reset_and_seed(db)
    import psycopg2

    with psycopg2.connect(db) as conn, conn.cursor() as cur:
        cur.execute("INSERT INTO comments (ticket_id, body) VALUES (1, 'Looking into it')")

    comments = list_comments(1)

    assert comments == [{"id": 1, "ticket_id": 1, "body": "Looking into it"}]


def test_list_attachments_returns_attachments_for_the_ticket(db):
    reset_and_seed(db)
    import psycopg2

    with psycopg2.connect(db) as conn, conn.cursor() as cur:
        cur.execute("INSERT INTO attachments (ticket_id, filename) VALUES (1, 'photo.jpg')")

    attachments = list_attachments(1)

    assert attachments == [{"id": 1, "ticket_id": 1, "filename": "photo.jpg"}]


def test_get_change_request_returns_the_matching_change_request(db):
    reset_and_seed(db)

    cr = get_change_request(1)

    assert cr == {
        "id": 1,
        "repo_id": 1,
        "title": "Fix rounding error in invoice totals",
        "diff": "--- a/invoice.py\n+++ b/invoice.py\n",
        "status": "open",
    }


def test_get_change_request_returns_none_for_an_unknown_id(db):
    reset_and_seed(db)

    assert get_change_request(999) is None


def test_find_change_request_by_title_returns_the_matching_change_request(db):
    reset_and_seed(db)

    cr = find_change_request_by_title("Add retry to payment webhook")

    assert cr["title"] == "Add retry to payment webhook"


def test_find_change_request_by_title_returns_none_for_an_unknown_title(db):
    reset_and_seed(db)

    assert find_change_request_by_title("no such change request") is None


def test_list_review_comments_returns_comments_for_the_change_request(db):
    reset_and_seed(db)
    import psycopg2

    with psycopg2.connect(db) as conn, conn.cursor() as cur:
        cur.execute("INSERT INTO review_comments (change_request_id, body) VALUES (1, 'Off by one')")

    comments = list_review_comments(1)

    assert comments == [{"id": 1, "change_request_id": 1, "body": "Off by one"}]


def test_get_runbook_returns_the_matching_runbook(db):
    reset_and_seed(db)

    runbook = get_runbook(1)

    assert runbook == {
        "id": 1,
        "repo_id": 1,
        "title": "Rolling back a bad billing deploy",
        "body": "1. Halt traffic. 2. Redeploy last tag.",
        "internal_notes": (
            "Escalate to payments-oncall before rolling back; "
            "past rollbacks corrupted the ledger."
        ),
    }


def test_get_runbook_returns_none_for_an_unknown_id(db):
    reset_and_seed(db)

    assert get_runbook(999) is None


def test_list_runbook_acknowledgements_returns_notes_for_the_runbook(db):
    reset_and_seed(db)
    import psycopg2

    with psycopg2.connect(db) as conn, conn.cursor() as cur:
        cur.execute("INSERT INTO runbook_acknowledgements (runbook_id, note) VALUES (1, 'Reviewed')")

    acks = list_runbook_acknowledgements(1)

    assert acks == [{"id": 1, "runbook_id": 1, "note": "Reviewed"}]


def test_get_deploy_returns_the_matching_deploy(db):
    reset_and_seed(db)
    import psycopg2

    with psycopg2.connect(db) as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO deploys (repo_id, environment, status) VALUES (1, 'production', 'succeeded')"
        )

    deploy = get_deploy(1)

    assert deploy == {"id": 1, "repo_id": 1, "environment": "production", "status": "succeeded"}


def test_get_deploy_returns_none_for_an_unknown_id(db):
    reset_and_seed(db)

    assert get_deploy(999) is None


def test_find_deploy_by_repo_and_environment_returns_the_most_recent_match(db):
    reset_and_seed(db)
    import psycopg2

    with psycopg2.connect(db) as conn, conn.cursor() as cur:
        cur.execute("INSERT INTO deploys (repo_id, environment) VALUES (1, 'production')")
        cur.execute(
            "INSERT INTO deploys (repo_id, environment, status) VALUES (1, 'production', 'succeeded')"
        )

    deploy = find_deploy_by_repo_and_environment(repo_id=1, environment="production")

    assert deploy == {"id": 2, "repo_id": 1, "environment": "production", "status": "succeeded"}


def test_find_deploy_by_repo_and_environment_returns_none_for_no_match(db):
    reset_and_seed(db)

    assert find_deploy_by_repo_and_environment(repo_id=1, environment="production") is None

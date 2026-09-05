"""Tests for the eight stateful_session review tasks' verify.py scripts.

Each verify.py is run exactly as the harness does: a subprocess reading
DATABASE_URL from the environment. Same shape as
test_verify_customer_resolutions.py.
"""

import os
import subprocess
import sys
from pathlib import Path

import psycopg2
import pytest

from backend.seed import reset_and_seed

TASKS_ROOT = Path(__file__).resolve().parent.parent / "tasks/stateful_session/standard/reviews"

# (task_id, change request title, comments in order, verdict)
REVIEWS = [
    (
        "rounding_fix",
        "Fix rounding error in invoice totals",
        [
            "Looks correct, but please add a unit test for the negative-cents case.",
            "LGTM otherwise.",
        ],
        "approved",
    ),
    (
        "webhook_retry",
        "Add retry to payment webhook",
        [
            "What's the max retry count?",
            "Please add exponential backoff.",
            "LGTM once that's addressed.",
        ],
        "changes_requested",
    ),
    (
        "cart_speed",
        "Speed up cart page load",
        ["Nice improvement, can you add a benchmark?", "LGTM."],
        "approved",
    ),
    (
        "cache_search",
        "Cache product search results",
        [
            "What's the cache TTL?",
            "Please invalidate on inventory update.",
            "LGTM after that.",
        ],
        "changes_requested",
    ),
    (
        "token_expiry",
        "Fix auth token expiry check",
        ["Good catch.", "LGTM."],
        "approved",
    ),
    (
        "rate_limit_login",
        "Add rate limiting to login endpoint",
        [
            "What's the rate limit threshold?",
            "Please log throttled attempts.",
            "LGTM once logged.",
        ],
        "changes_requested",
    ),
    (
        "batch_email",
        "Batch email notifications",
        ["Nice batching logic.", "LGTM."],
        "approved",
    ),
    (
        "dedupe_sms",
        "Fix duplicate SMS alerts",
        ["Please add a test for the dedupe window.", "LGTM after tests."],
        "changes_requested",
    ),
]


def run_verify(task_id: str, database_url: str) -> subprocess.CompletedProcess:
    verify_path = TASKS_ROOT / task_id / "verify.py"
    return subprocess.run(
        [sys.executable, str(verify_path)],
        capture_output=True,
        text=True,
        env={**os.environ, "DATABASE_URL": database_url},
    )


def _review(database_url, title, comments, status):
    with psycopg2.connect(database_url) as conn, conn.cursor() as cur:
        for body in comments:
            cur.execute(
                "INSERT INTO review_comments (change_request_id, body) "
                "SELECT id, %s FROM change_requests WHERE title = %s",
                (body, title),
            )
        cur.execute("UPDATE change_requests SET status = %s WHERE title = %s", (status, title))


@pytest.mark.parametrize("task_id, title, comments, verdict", REVIEWS)
def test_verify_passes_when_reviewed_in_order_and_submitted(db, task_id, title, comments, verdict):
    reset_and_seed(db)
    _review(db, title, comments, verdict)

    result = run_verify(task_id, db)

    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("task_id, title, comments, verdict", REVIEWS)
def test_verify_fails_when_never_reviewed(db, task_id, title, comments, verdict):
    reset_and_seed(db)

    result = run_verify(task_id, db)

    assert result.returncode != 0


@pytest.mark.parametrize("task_id, title, comments, verdict", REVIEWS)
def test_verify_fails_when_the_verdict_is_wrong(db, task_id, title, comments, verdict):
    reset_and_seed(db)
    wrong_verdict = "changes_requested" if verdict == "approved" else "approved"
    _review(db, title, comments, wrong_verdict)

    result = run_verify(task_id, db)

    assert result.returncode != 0


@pytest.mark.parametrize("task_id, title, comments, verdict", REVIEWS)
def test_verify_fails_when_a_comment_is_missing(db, task_id, title, comments, verdict):
    reset_and_seed(db)
    _review(db, title, comments[:-1], verdict)

    result = run_verify(task_id, db)

    assert result.returncode != 0

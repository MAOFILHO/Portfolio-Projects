"""Shared Postgres-reading helper for tool_orchestrator verifiers.

Every verify.py reads final state through this one place, so a change to how
state is read (schema, connection, namespace) only happens once.
"""

import os

import psycopg2
import psycopg2.extras


def _connect():
    return psycopg2.connect(
        os.environ["DATABASE_URL"], cursor_factory=psycopg2.extras.RealDictCursor
    )


def get_ticket(ticket_id: int) -> dict | None:
    conn = _connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, title, status, assignee FROM tickets WHERE id = %s", (ticket_id,)
            )
            row = cur.fetchone()
            return dict(row) if row else None
    finally:
        conn.close()


def find_ticket_by_title(title: str) -> dict | None:
    """Return the most recently created ticket with this title, or None.

    Verifiers know the title a task asked the agent to use, not the id a
    server assigns it, so they look tickets up by title.
    """
    conn = _connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, title, status, assignee FROM tickets "
                "WHERE title = %s ORDER BY id DESC LIMIT 1",
                (title,),
            )
            row = cur.fetchone()
            return dict(row) if row else None
    finally:
        conn.close()


def list_comments(ticket_id: int) -> list[dict]:
    conn = _connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, ticket_id, body FROM comments WHERE ticket_id = %s ORDER BY id",
                (ticket_id,),
            )
            return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()


def list_attachments(ticket_id: int) -> list[dict]:
    conn = _connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, ticket_id, filename FROM attachments WHERE ticket_id = %s ORDER BY id",
                (ticket_id,),
            )
            return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()


def get_change_request(change_request_id: int) -> dict | None:
    conn = _connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, repo_id, title, diff, status FROM change_requests WHERE id = %s",
                (change_request_id,),
            )
            row = cur.fetchone()
            return dict(row) if row else None
    finally:
        conn.close()


def find_change_request_by_title(title: str) -> dict | None:
    """Return the most recently created change request with this title, or
    None. Mirrors find_ticket_by_title: verifiers know the title a task
    named, not the id a server assigns it."""
    conn = _connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, repo_id, title, diff, status FROM change_requests "
                "WHERE title = %s ORDER BY id DESC LIMIT 1",
                (title,),
            )
            row = cur.fetchone()
            return dict(row) if row else None
    finally:
        conn.close()


def list_review_comments(change_request_id: int) -> list[dict]:
    conn = _connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, change_request_id, body FROM review_comments "
                "WHERE change_request_id = %s ORDER BY id",
                (change_request_id,),
            )
            return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()


def get_deploy(deploy_id: int) -> dict | None:
    conn = _connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, repo_id, environment, status FROM deploys WHERE id = %s",
                (deploy_id,),
            )
            row = cur.fetchone()
            return dict(row) if row else None
    finally:
        conn.close()


def find_deploy_by_repo_and_environment(repo_id: int, environment: str) -> dict | None:
    """Return the most recently created deploy for this repo/environment, or
    None. Verifiers know the repo and environment a task targeted, not the id
    a server assigns the deploy."""
    conn = _connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, repo_id, environment, status FROM deploys "
                "WHERE repo_id = %s AND environment = %s ORDER BY id DESC LIMIT 1",
                (repo_id, environment),
            )
            row = cur.fetchone()
            return dict(row) if row else None
    finally:
        conn.close()


def get_runbook(runbook_id: int) -> dict | None:
    conn = _connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, repo_id, title, body, internal_notes FROM runbooks WHERE id = %s",
                (runbook_id,),
            )
            row = cur.fetchone()
            return dict(row) if row else None
    finally:
        conn.close()


def list_runbook_acknowledgements(runbook_id: int) -> list[dict]:
    conn = _connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, runbook_id, note FROM runbook_acknowledgements "
                "WHERE runbook_id = %s ORDER BY id",
                (runbook_id,),
            )
            return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()

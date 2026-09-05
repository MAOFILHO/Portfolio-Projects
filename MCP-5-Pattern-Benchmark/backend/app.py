"""HTTP API for the /tickets namespace.

A small FastAPI service in front of Postgres: list, create, get, update, add
comment, add attachment. Both the control (server_wrapper) and pattern
(server_orchestrator) MCP servers call this over HTTP; it holds no MCP
concepts of its own.
"""

import os

import psycopg2
import psycopg2.extras
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI()


class CreateTicket(BaseModel):
    title: str
    description: str = ""
    customer_id: int | None = None


class UpdateTicket(BaseModel):
    status: str | None = None
    assignee: str | None = None


class AddComment(BaseModel):
    body: str


class AddAttachment(BaseModel):
    filename: str


class AddReviewComment(BaseModel):
    body: str


class AddRunbookAcknowledgement(BaseModel):
    note: str


class UpdateChangeRequest(BaseModel):
    status: str | None = None


class CreateDeploy(BaseModel):
    repo_id: int
    environment: str


class UpdateDeploy(BaseModel):
    status: str | None = None


def _connect():
    return psycopg2.connect(
        os.environ["DATABASE_URL"], cursor_factory=psycopg2.extras.RealDictCursor
    )


@app.get("/tickets")
def list_tickets():
    with _connect() as conn, conn.cursor() as cur:
        cur.execute("SELECT id, title, status, assignee FROM tickets ORDER BY id")
        return [dict(row) for row in cur.fetchall()]


@app.post("/tickets")
def create_ticket(ticket: CreateTicket):
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO tickets (title, description, customer_id) VALUES (%s, %s, %s) "
            "RETURNING id, title, status, assignee",
            (ticket.title, ticket.description, ticket.customer_id),
        )
        return dict(cur.fetchone())


@app.get("/tickets/{ticket_id}/customer")
def get_ticket_customer(ticket_id: int):
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT c.id, c.name, c.tier FROM customers c "
            "JOIN tickets t ON t.customer_id = c.id WHERE t.id = %s",
            (ticket_id,),
        )
        row = cur.fetchone()
        if row is None:
            raise HTTPException(
                status_code=404, detail=f"no customer linked to ticket {ticket_id}"
            )
        return dict(row)


@app.get("/tickets/{ticket_id}")
def get_ticket(ticket_id: int):
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT id, title, status, assignee FROM tickets WHERE id = %s", (ticket_id,)
        )
        row = cur.fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail=f"no ticket with id {ticket_id}")
        return dict(row)


@app.post("/tickets/{ticket_id}/comments")
def add_comment(ticket_id: int, comment: AddComment):
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO comments (ticket_id, body) VALUES (%s, %s) "
            "RETURNING id, ticket_id, body",
            (ticket_id, comment.body),
        )
        return dict(cur.fetchone())


@app.post("/tickets/{ticket_id}/attachments")
def add_attachment(ticket_id: int, attachment: AddAttachment):
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO attachments (ticket_id, filename) VALUES (%s, %s) "
            "RETURNING id, ticket_id, filename",
            (ticket_id, attachment.filename),
        )
        return dict(cur.fetchone())


@app.get("/runbooks")
def list_runbooks(repo_id: int):
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT id, repo_id, title, body, internal_notes FROM runbooks "
            "WHERE repo_id = %s ORDER BY id",
            (repo_id,),
        )
        return [dict(row) for row in cur.fetchall()]


@app.get("/runbooks/{runbook_id}")
def get_runbook(runbook_id: int):
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT id, repo_id, title, body, internal_notes FROM runbooks WHERE id = %s",
            (runbook_id,),
        )
        row = cur.fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail=f"no runbook with id {runbook_id}")
        return dict(row)


@app.post("/runbooks/{runbook_id}/acknowledgements")
def add_runbook_acknowledgement(runbook_id: int, ack: AddRunbookAcknowledgement):
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO runbook_acknowledgements (runbook_id, note) VALUES (%s, %s) "
            "RETURNING id, runbook_id, note",
            (runbook_id, ack.note),
        )
        return dict(cur.fetchone())


@app.get("/runbooks/{runbook_id}/acknowledgements")
def list_runbook_acknowledgements(runbook_id: int):
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT id, runbook_id, note FROM runbook_acknowledgements "
            "WHERE runbook_id = %s ORDER BY id",
            (runbook_id,),
        )
        return [dict(row) for row in cur.fetchall()]


@app.post("/deploys")
def create_deploy(deploy: CreateDeploy):
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO deploys (repo_id, environment) VALUES (%s, %s) "
            "RETURNING id, repo_id, environment, status",
            (deploy.repo_id, deploy.environment),
        )
        return dict(cur.fetchone())


@app.get("/deploys/{deploy_id}")
def get_deploy(deploy_id: int):
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT id, repo_id, environment, status FROM deploys WHERE id = %s",
            (deploy_id,),
        )
        row = cur.fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail=f"no deploy with id {deploy_id}")
        return dict(row)


@app.patch("/deploys/{deploy_id}")
def update_deploy_status(deploy_id: int, update: UpdateDeploy):
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(
            "UPDATE deploys SET status = COALESCE(%s, status) "
            "WHERE id = %s RETURNING id, repo_id, environment, status",
            (update.status, deploy_id),
        )
        row = cur.fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail=f"no deploy with id {deploy_id}")
        return dict(row)


@app.get("/repos/{repo_id}/change-requests")
def list_change_requests(repo_id: int):
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT id, repo_id, title, status FROM change_requests "
            "WHERE repo_id = %s ORDER BY id",
            (repo_id,),
        )
        return [dict(row) for row in cur.fetchall()]


@app.get("/change-requests")
def list_all_change_requests():
    with _connect() as conn, conn.cursor() as cur:
        cur.execute("SELECT id, repo_id, title, status FROM change_requests ORDER BY id")
        return [dict(row) for row in cur.fetchall()]


@app.get("/change-requests/{change_request_id}")
def get_change_request(change_request_id: int):
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT id, repo_id, title, diff, status FROM change_requests WHERE id = %s",
            (change_request_id,),
        )
        row = cur.fetchone()
        if row is None:
            raise HTTPException(
                status_code=404, detail=f"no change request with id {change_request_id}"
            )
        return dict(row)


@app.post("/change-requests/{change_request_id}/comments")
def add_review_comment(change_request_id: int, comment: AddReviewComment):
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO review_comments (change_request_id, body) VALUES (%s, %s) "
            "RETURNING id, change_request_id, body",
            (change_request_id, comment.body),
        )
        return dict(cur.fetchone())


@app.get("/change-requests/{change_request_id}/comments")
def list_review_comments(change_request_id: int):
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT id, change_request_id, body FROM review_comments "
            "WHERE change_request_id = %s ORDER BY id",
            (change_request_id,),
        )
        return [dict(row) for row in cur.fetchall()]


@app.patch("/change-requests/{change_request_id}")
def update_change_request(change_request_id: int, update: UpdateChangeRequest):
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(
            "UPDATE change_requests SET status = COALESCE(%s, status) "
            "WHERE id = %s RETURNING id, repo_id, title, diff, status",
            (update.status, change_request_id),
        )
        row = cur.fetchone()
        if row is None:
            raise HTTPException(
                status_code=404, detail=f"no change request with id {change_request_id}"
            )
        return dict(row)


@app.patch("/tickets/{ticket_id}")
def update_ticket(ticket_id: int, update: UpdateTicket):
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(
            "UPDATE tickets SET "
            "status = COALESCE(%s, status), assignee = COALESCE(%s, assignee) "
            "WHERE id = %s RETURNING id, title, status, assignee",
            (update.status, update.assignee, ticket_id),
        )
        row = cur.fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail=f"no ticket with id {ticket_id}")
        return dict(row)

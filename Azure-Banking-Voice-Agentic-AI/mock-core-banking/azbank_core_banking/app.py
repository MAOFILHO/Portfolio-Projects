"""The HTTP face of the system of record. REST-resource routes over the rules in db.py.

**The status mapping is the contract** (docs/phase3/exit-criteria.md, criterion 3), and the whole
reason the voice agent can tell three outcomes apart:

    unknown account           -> 404   the client raises (T-UNKNOWN-ACCT)
    declined by business rule -> 200   a normal outcome of a working system, carrying the real
                                       available amount
    malformed request         -> 422   the caller has a bug; nobody has been refused anything
    anything unexpected       -> 5xx   the client treats it as unavailable

A decline is deliberately **not** a 4xx. Mapping it to one would put it in the same bucket as
unknown-account and blur the distinction T-UNKNOWN-ACCT rests on.

**No response body ever contains a caller-facing sentence.** This service returns data and outcome
codes; every sentence the caller hears is composed in the voice agent. That is asserted
mechanically by tests/test_api.py rather than trusted, because the module this service replaces got
it exactly backwards -- it returned a ready-made apology from what was, in effect, the system of
record.
"""
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from . import db

#: Where the SQLite file lives. Container Apps' filesystem is ephemeral and no volume is mounted,
#: so this resets with the container -- which is the intended demo behaviour, not an oversight
#: (docs/phase3/exit-criteria.md). Overridable so tests can use ":memory:".
DATABASE_ENV_VAR = "CORE_BANKING_DB"
DEFAULT_DATABASE = "/tmp/core-banking.sqlite3"


class TransferRequest(BaseModel):
    """`amount_cents` is constrained here so a non-positive amount is a 422 from the framework
    rather than something every route has to remember to check. Cents, never dollars -- the wire
    format matches the storage format, and the dollars conversion happens once in the voice
    agent."""

    from_account: str
    to_account: str
    amount_cents: int = Field(gt=0)


def _unknown_account(error):
    """The 404 for an unknown account, **naming the account**.

    Naming it is not a nicety: the voice agent has to tell the caller which account it couldn't
    find, and the system of record is the only thing that knows which of a transfer's two accounts
    was the bad one. Without this the client has nothing account-shaped to put in the sentence --
    and the first version of that client reached for the request URL instead, which meant a caller
    heard the service's internal hostname read out loud (found by /code-review, 2026-09-08).
    """
    return HTTPException(
        status_code=404, detail={"error": "unknown_account", "account": str(error.args[0])}
    )


def build_app(database=None):
    """Construct the app against a given database.

    Takes the database rather than reading the environment at import time, so tests get a fresh
    in-memory one per case with no file, no shared state, and no monkeypatching -- the same
    injection reasoning the voice agent applies to its own collaborators.
    """
    if database is None:
        database = os.environ.get(DATABASE_ENV_VAR, DEFAULT_DATABASE)
    conn = db.connect(database)

    @asynccontextmanager
    async def lifespan(_app):
        yield
        conn.close()

    app = FastAPI(title="mock-core-banking", lifespan=lifespan)

    @app.get("/health")
    def health():
        """Liveness only -- deliberately does not touch account state, so a probe can never be
        the thing that wakes or contends with the database."""
        return {"status": "ok"}

    @app.get("/accounts")
    def list_accounts():
        return {
            "accounts": [
                {"name": name, "balance_cents": balance}
                for name, balance in db.list_accounts(conn).items()
            ]
        }

    @app.get("/accounts/{account}")
    def get_account(account: str):
        try:
            balance = db.get_balance(conn, account)
        except db.UnknownAccount as e:
            # 404, and nothing else: no default balance, no zero, no nearest match.
            raise _unknown_account(e) from None
        return {"name": account, "balance_cents": balance}

    @app.post("/transfers")
    def create_transfer(request: TransferRequest):
        try:
            result = db.transfer(
                conn, request.from_account, request.to_account, request.amount_cents
            )
        except db.UnknownAccount as e:
            raise _unknown_account(e) from None
        if result.outcome == "declined":
            # 200: the system worked and said no. See the module docstring.
            return {
                "outcome": "declined",
                "reason": result.reason,
                "available_cents": result.available_cents,
            }
        return {
            "outcome": "completed",
            "from_balance_cents": result.from_balance_cents,
            "to_balance_cents": result.to_balance_cents,
        }

    return app


# No module-level `app = build_app()`. Importing this module must not open a database or create a
# file -- a test that imports build_app would otherwise get a real SQLite file in /tmp as a side
# effect of the import. The Dockerfile serves this with uvicorn's `--factory` flag instead, which
# calls build_app() at startup, where the side effect belongs.

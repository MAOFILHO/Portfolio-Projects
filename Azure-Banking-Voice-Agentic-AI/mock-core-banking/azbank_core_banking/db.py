"""Account state and the rules that govern it. The system of record (CONTEXT.md).

**Money is integer cents, everywhere in this module.** Not a float -- the Phase 1 module this
service replaces held balances as floats because it was an in-memory demo dict that reset on every
restart, and nothing that persists money should inherit that. The conversion to dollars happens
once, at the presentation boundary in the voice agent, and never here.

**Business rules live here, not in the caller.** Whether a transfer is allowed is the system of
record's decision. A caller that could decide for itself whether it had enough money would not be
talking to a system of record.

Deliberately stdlib `sqlite3` and hand-written SQL: five statements against one table does not earn
an ORM dependency, and the schema is small enough to read in full.
"""
import sqlite3
from dataclasses import dataclass

#: The demo accounts, in cents. Same two accounts and same balances the in-memory Phase 1 module
#: held ($2,400.00 and $500.00), so a demo behaves identically across the change of backend.
SEED_ACCOUNTS = {"chequing": 240000, "savings": 50000}

_SCHEMA = """
CREATE TABLE IF NOT EXISTS accounts (
    name          TEXT    PRIMARY KEY,
    balance_cents INTEGER NOT NULL
)
"""


class UnknownAccount(LookupError):
    """A named account does not exist.

    Raised, never resolved to a default, a zero, or another account's balance. This is the
    behaviour `T-UNKNOWN-ACCT` is named for and the one CLAUDE.md's hard exclusions call out by
    example: the reference repo this project was seeded from returned a fixed $1,000.00 for any
    unknown account, which is a silent-fallback bug wearing the costume of a working feature.
    """


@dataclass(frozen=True)
class TransferResult:
    """What happened to a transfer. Two shapes, one type, distinguished by `outcome`.

    `completed` carries the resulting balances; `declined` carries the reason and the real amount
    available. A decline is a normal outcome of a working system -- it is not an error, and the
    fields that are None for one outcome are simply not part of that outcome.
    """

    outcome: str
    from_balance_cents: int | None = None
    to_balance_cents: int | None = None
    reason: str | None = None
    available_cents: int | None = None


def initialise(conn):
    """Creates the schema if absent and seeds the accounts **only if the table is empty**.

    Seeding is "if empty", never "on every boot": Container Apps' filesystem is ephemeral, so a
    fresh container legitimately starts from the demo state, but a restart of a container that has
    a database must not silently undo whatever is in it.
    """
    conn.execute(_SCHEMA)
    already_seeded = conn.execute("SELECT COUNT(*) FROM accounts").fetchone()[0] > 0
    if not already_seeded:
        conn.executemany(
            "INSERT INTO accounts (name, balance_cents) VALUES (?, ?)",
            sorted(SEED_ACCOUNTS.items()),
        )
    conn.commit()


def list_accounts(conn):
    """Every account and its balance in cents, ordered by name so responses are stable."""
    rows = conn.execute("SELECT name, balance_cents FROM accounts ORDER BY name").fetchall()
    return {name: balance for name, balance in rows}


def get_balance(conn, account):
    """The balance of one account, in cents. Raises UnknownAccount if it does not exist."""
    row = conn.execute(
        "SELECT balance_cents FROM accounts WHERE name = ?", (account,)
    ).fetchone()
    if row is None:
        raise UnknownAccount(account)
    return row[0]


def transfer(conn, from_account, to_account, amount_cents):
    """Move money between two accounts. Returns a TransferResult; raises only for bad inputs.

    The three outcomes are kept distinct on purpose (CONTEXT.md): an unknown account **raises**, an
    overdrawing transfer is **declined** and mutates nothing, and a valid transfer **completes**
    atomically. A non-positive amount is a malformed request rather than a business decline, so it
    raises too -- the caller has a bug, the account holder has not been refused anything. The same
    account on both sides is malformed for the same reason.
    """
    if amount_cents <= 0:
        raise ValueError(f"transfer amount must be positive, got {amount_cents!r}")
    if from_account == to_account:
        # Rejected rather than performed as a no-op. Both UPDATEs below would land on the same row
        # and cancel out, leaving storage untouched while the return below reported
        # `available - amount_cents` -- a balance this service had never held, which the voice
        # agent then read to the caller as fact (/code-review, 2026-09-08). The rule that no
        # failure path may produce a fabricated figure has no exception for the happy path.
        raise ValueError(f"transfer needs two different accounts, got {from_account!r} twice")

    # Read both balances first: an unknown *destination* must raise before any debit happens, not
    # after. Doing this inside the transaction below would still be correct, but this way there is
    # no window in which a rollback is what protects the caller.
    available = get_balance(conn, from_account)
    destination = get_balance(conn, to_account)

    if amount_cents > available:
        return TransferResult(
            outcome="declined", reason="insufficient_funds", available_cents=available
        )

    # `with conn` is sqlite3's transaction context: both updates commit together or neither does.
    with conn:
        conn.execute(
            "UPDATE accounts SET balance_cents = balance_cents - ? WHERE name = ?",
            (amount_cents, from_account),
        )
        conn.execute(
            "UPDATE accounts SET balance_cents = balance_cents + ? WHERE name = ?",
            (amount_cents, to_account),
        )
    return TransferResult(
        outcome="completed",
        from_balance_cents=available - amount_cents,
        to_balance_cents=destination + amount_cents,
    )


def connect(database):
    """Open a connection and ensure the schema and seed exist.

    `check_same_thread=False` because the service is served by an ASGI worker that may touch the
    connection from more than one thread; the workload here is a handful of statements against one
    small table, so a single connection is simpler and entirely sufficient.
    """
    conn = sqlite3.connect(database, check_same_thread=False)
    initialise(conn)
    return conn

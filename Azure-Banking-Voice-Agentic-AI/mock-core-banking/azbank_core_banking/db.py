"""Account state and the rules that govern it. The system of record (CONTEXT.md).

**Money is integer cents, everywhere in this module.** Not a float -- the Phase 1 module this
service replaces held balances as floats because it was an in-memory demo dict that reset on every
restart, and nothing that persists money should inherit that. The conversion to dollars happens
once, at the presentation boundary in the voice agent, and never here.

**Business rules live here, not in the caller.** Whether a transfer is allowed is the system of
record's decision. A caller that could decide for itself whether it had enough money would not be
talking to a system of record.

**The credential is stored as a digest, never as a PIN.** That is what lets B2's artifact scan cover
the database file with no carve-out: a scan that had to skip a column would be a scan that could be
made to pass by moving the leak into it. Nothing in this module ever writes, returns, formats, or
raises the submitted value.

Deliberately stdlib `sqlite3` and hand-written SQL: a handful of statements against two small tables
does not earn an ORM dependency, and the schema is small enough to read in full. The digest is
stdlib `hashlib` for the same reason -- see SEED_CREDENTIAL_DIGEST for why it is unsalted.
"""
import hashlib
import hmac
import sqlite3
import threading
from dataclasses import dataclass

#: Serialises every function here, because the service is **one connection** shared by every
#: request: `build_app` opens it once and closes over it, and FastAPI runs `def` routes on a
#: threadpool. sqlite3 reports `threadsafety == 3`, so the *library* is happy to be shared -- what
#: is not shareable is the connection's **transaction state**. `with conn:` is per-connection, not
#: per-caller, so two in-flight requests were inside one implicit transaction: SQLite answered
#: "cannot start a transaction within a transaction", a SELECT for an account that plainly exists
#: came back empty, and two transfers could both pass the sufficiency check and overdraw the
#: account (/code-review, 2026-09-08, measured at ~30% of attempts with four threads).
#:
#: A lock rather than a connection per request: the whole service is a handful of statements
#: against one small table, so serialising costs nothing worth measuring, and it keeps `:memory:`
#: usable in tests -- a per-request connection would hand each request its own empty database.
#: Reentrant because `transfer` calls `get_balance`.
_LOCK = threading.RLock()

#: The demo accounts, in cents. Same two accounts and same balances the in-memory Phase 1 module
#: held ($2,400.00 and $500.00), so a demo behaves identically across the change of backend.
SEED_ACCOUNTS = {"chequing": 240000, "savings": 50000}

#: The demo PIN, in the clear, in source. A published constant of a prototype -- not a secret this
#: file is failing to keep. B2 forbids the PIN in a transcript, a log line, a span attribute or a
#: persisted record; source code is none of those, and the B2 scanner needs a value to search for.
DEMO_PIN = "1234"

#: What the database actually holds. Unsalted and stdlib-only, deliberately: a four-digit PIN whose
#: value is published gets nothing from a KDF -- an attacker who reads this file already has the
#: PIN, and one who reads only the database can exhaust ten thousand candidates whatever the
#: derivation costs. A stated prototype choice, and the line where production would differ.
SEED_CREDENTIAL_DIGEST = hashlib.sha256(DEMO_PIN.encode()).hexdigest()

#: One row, always, because there is one profile (CONTEXT.md): a single set of credentials and
#: accounts that authentication unlocks and that never identifies anyone. The CHECK is what says so
#: in the schema rather than in a comment -- a second credential cannot be inserted.
_SCHEMA = """
CREATE TABLE IF NOT EXISTS accounts (
    name          TEXT    PRIMARY KEY,
    balance_cents INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS credentials (
    id         INTEGER PRIMARY KEY CHECK (id = 1),
    pin_digest TEXT NOT NULL
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

    `completed` carries the resulting balances and the amount that was actually applied; `declined`
    carries the reason and the real amount available. A decline is a normal outcome of a working
    system -- it is not an error, and the fields that are None for one outcome are simply not part
    of that outcome.

    `moved_cents` is reported for the same reason the balances are: the voice agent speaks it
    ("transferred $X"), and every figure in that sentence has to come from the system of record.
    The client can see what it sent, but what it sent is not evidence of what was applied
    (/code-review, 2026-09-09).
    """

    outcome: str
    from_balance_cents: int | None = None
    to_balance_cents: int | None = None
    moved_cents: int | None = None
    reason: str | None = None
    available_cents: int | None = None


def initialise(conn):
    """Creates the schema if absent and seeds accounts and credential **only if empty**.

    Seeding is "if empty", never "on every boot": Container Apps' filesystem is ephemeral, so a
    fresh container legitimately starts from the demo state, but a restart of a container that has
    a database must not silently undo whatever is in it. The credential gets the same rule as the
    balances, and for the same reason.

    `executescript` rather than `execute`, because the schema is now two statements. It issues a
    COMMIT of its own first, which is harmless here: this runs at connect time, before any request
    can have a transaction open.
    """
    with _LOCK:
        conn.executescript(_SCHEMA)
        already_seeded = conn.execute("SELECT COUNT(*) FROM accounts").fetchone()[0] > 0
        if not already_seeded:
            conn.executemany(
                "INSERT INTO accounts (name, balance_cents) VALUES (?, ?)",
                sorted(SEED_ACCOUNTS.items()),
            )
        credential_seeded = conn.execute("SELECT COUNT(*) FROM credentials").fetchone()[0] > 0
        if not credential_seeded:
            conn.execute(
                "INSERT INTO credentials (id, pin_digest) VALUES (1, ?)",
                (SEED_CREDENTIAL_DIGEST,),
            )
        conn.commit()


def credential_digest(conn):
    """The stored digest. Exposed so a test can pin what was seeded without reaching for SQL."""
    with _LOCK:
        row = conn.execute("SELECT pin_digest FROM credentials WHERE id = 1").fetchone()
    return None if row is None else row[0]


def verify_pin(conn, pin):
    """Does this PIN match the profile's credential? True or False, and nothing else.

    **Refuses rather than raises, whatever it is handed.** The rest of this module raises on a
    malformed input -- a fractional amount, an unknown account -- and formats the offending value
    into the message, which is the right call for money and exactly the wrong one here: an
    exception carrying a rejected credential is an exception whose message is the leak. There is no
    PIN malformed enough to be worth repeating back, so anything that cannot be compared is simply
    not a match. That fails closed for free, which is the direction this control has to fail in.

    The comparison is `hmac.compare_digest`, so the check itself teaches an attacker nothing about
    how much of a wrong PIN was right: both operands are fixed-length hex digests, and the compare
    does not stop at the first differing character the way `==` does.
    """
    if not isinstance(pin, str):
        return False
    stored = credential_digest(conn)
    if stored is None:
        return False
    # `errors="replace"` so that a lone surrogate -- the one str a UTF-8 encode refuses -- is
    # refused like every other non-match instead of raising out of a function that promises not to.
    candidate = hashlib.sha256(pin.encode(errors="replace")).hexdigest()
    return hmac.compare_digest(stored, candidate)


def list_accounts(conn):
    """Every account and its balance in cents, ordered by name so responses are stable."""
    with _LOCK:
        rows = conn.execute("SELECT name, balance_cents FROM accounts ORDER BY name").fetchall()
    return {name: balance for name, balance in rows}


def get_balance(conn, account):
    """The balance of one account, in cents. Raises UnknownAccount if it does not exist."""
    with _LOCK:
        row = conn.execute(
            "SELECT balance_cents FROM accounts WHERE name = ?", (account,)
        ).fetchone()
    if row is None:
        raise UnknownAccount(account)
    return row[0]


def _require_account(conn, account):
    """Raise UnknownAccount unless the account exists. Named for the raise, because that is the
    whole reason to call it -- `get_balance(conn, x)` on a line that discards the balance reads
    like a no-op someone forgot to delete."""
    get_balance(conn, account)


def transfer(conn, from_account, to_account, amount_cents):
    """Move money between two accounts. Returns a TransferResult; raises only for bad inputs.

    The outcomes are kept distinct on purpose (CONTEXT.md): an unknown account **raises**, an
    overdrawing transfer is **declined** and mutates nothing, and a valid transfer **completes**
    atomically. A non-positive amount is a malformed request rather than a business decline, so it
    raises too -- the caller has a bug, the account holder has not been refused anything. So is a
    fractional one: cents are whole or they are not cents, and a float reaching an INTEGER column
    is stored REAL, which is the one way a value that is not integer cents can enter persistence.
    """
    if not isinstance(amount_cents, int) or isinstance(amount_cents, bool):
        raise ValueError(f"transfer amount must be whole cents, got {amount_cents!r}")
    if amount_cents <= 0:
        raise ValueError(f"transfer amount must be positive, got {amount_cents!r}")

    # The lock spans read, check and write together, which is the whole point of it: `available`
    # informs a decision that the UPDATE below then acts on, so anything that can run between the
    # two can spend the same money twice. Two concurrent requests for the full balance both passed
    # this check and left the account at -240000 (/code-review, 2026-09-08).
    with _LOCK:
        # Both accounts are checked first: an unknown *destination* must raise before any debit
        # happens, not after -- so there is no window in which a rollback is what protects the
        # caller.
        available = get_balance(conn, from_account)
        _require_account(conn, to_account)

        if amount_cents > available:
            return TransferResult(
                outcome="declined", reason="insufficient_funds", available_cents=available
            )

        # `with conn` is sqlite3's transaction context: both updates commit together or neither
        # does. The resulting balances are then **read back out of the table**, never computed as
        # `available - amount_cents`. The arithmetic and the storage agree for a transfer between
        # two different accounts, so the difference looks academic -- until both UPDATEs land on
        # the same row and cancel, at which point the arithmetic reports a balance this service has
        # never held and the voice agent reads it to the caller as fact (/code-review,
        # 2026-09-08). Reading back is what makes "the figures come from the system of record" true
        # by construction rather than true for the inputs someone happened to test.
        with conn:
            conn.execute(
                "UPDATE accounts SET balance_cents = balance_cents - ? WHERE name = ?",
                (amount_cents, from_account),
            )
            conn.execute(
                "UPDATE accounts SET balance_cents = balance_cents + ? WHERE name = ?",
                (amount_cents, to_account),
            )
            from_balance = get_balance(conn, from_account)
            to_balance = get_balance(conn, to_account)
    return TransferResult(
        outcome="completed",
        from_balance_cents=from_balance,
        to_balance_cents=to_balance,
        moved_cents=amount_cents,
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

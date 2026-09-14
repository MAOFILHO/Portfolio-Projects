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

**History is written by this module, not assembled by a caller** (issue #44). A completed transfer
records its own two lines inside the same transaction as the balance updates, so the history and the
balances cannot disagree -- the same reasoning that makes the resulting balances read back out of the
table rather than computed. A declined transfer records nothing, because nothing happened.

Deliberately stdlib `sqlite3` and hand-written SQL: a handful of statements against three small
tables does not earn an ORM dependency, and the schema is small enough to read in full. The digest is
stdlib `hashlib` for the same reason -- see SEED_CREDENTIAL_DIGEST for why it is unsalted.
"""
import hashlib
import hmac
import sqlite3
import threading
from dataclasses import dataclass
from datetime import UTC, datetime

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

#: How many transactions the service will return for one account, most recent first. **The bound is
#: the service's, not the model's restraint** (issue #44): a voice channel must never be handed a
#: payload it could not read aloud, and "the caller will probably not ask for more" is not a bound.
#: Five is what fits in a sentence a caller can follow on a phone without asking for it again.
TRANSACTION_LIST_LIMIT = 5

#: One row, always, because there is one profile (CONTEXT.md): a single set of credentials and
#: accounts that authentication unlocks and that never identifies anyone. The CHECK is what says so
#: in the schema rather than in a comment -- a second credential cannot be inserted.
#:
#: **`transactions` holds no prose** (issue #44). `kind` and `counterparty` are tokens, and the
#: sentence a caller hears is composed in the voice agent from them -- the same rule the rest of this
#: service already keeps, and the inversion #26 criterion 8 exists to prevent. A `description` column
#: would have been a caller-facing sentence living in the system of record.
#:
#: `amount_cents` is **signed**: negative is money leaving this account. One transfer therefore
#: writes two rows, a debit on the source and a credit on the destination, which is what makes each
#: account's own history readable on its own. The CHECK is there because a zero-amount transaction is
#: not a thing that happened; `transfer` already refuses a non-positive amount before reaching here.
_SCHEMA = """
CREATE TABLE IF NOT EXISTS accounts (
    name          TEXT    PRIMARY KEY,
    balance_cents INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS credentials (
    id         INTEGER PRIMARY KEY CHECK (id = 1),
    pin_digest TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS transactions (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    account      TEXT    NOT NULL,
    kind         TEXT    NOT NULL,
    counterparty TEXT,
    amount_cents INTEGER NOT NULL CHECK (amount_cents <> 0),
    occurred_at  TEXT    NOT NULL
);
CREATE TABLE IF NOT EXISTS cards (
    id         INTEGER PRIMARY KEY CHECK (id = 1),
    status     TEXT NOT NULL CHECK (status IN ('active', 'blocked')),
    blocked_at TEXT
);
CREATE TABLE IF NOT EXISTS idempotency (
    key         TEXT PRIMARY KEY,
    outcome     TEXT NOT NULL,
    recorded_at TEXT NOT NULL
)
"""

#: The profile's single card is either of these and nothing else. The schema says so with a CHECK
#: rather than a comment, for the same reason the credentials table does: an invariant enforced by
#: the storage cannot be broken by a caller who did not read the comment.
CARD_ACTIVE = "active"
CARD_BLOCKED = "blocked"

#: What a block attempt did. **Both are a working system answering** -- neither is an error, and the
#: route returns 200 for either, the same standing a declined transfer already has.
#:
#: `BLOCKED` means this attempt is what blocked the card. `ALREADY_BLOCKED` means it was blocked
#: before this attempt arrived, whether by a replay of the same idempotency key or by an earlier
#: attempt under a different one. **The caller is told which**, because "I have blocked it" and "it
#: was already blocked" are different sentences and a caller who asked twice deserves the second.
BLOCKED = "blocked"
ALREADY_BLOCKED = "already_blocked"

#: The one kind of transaction this prototype can produce. Named rather than inlined so the voice
#: agent's sentence has a token to switch on and a second kind is a row rather than a rewrite.
TRANSFER = "transfer"

#: A small history on a fresh database, so a demo call has something to read on the first run rather
#: than an empty list (issue #44). Fixed timestamps, not relative ones: a demo that reads differently
#: depending on when the container started is a demo whose output nobody can check.
#:
#: **This history predates the seeded balances rather than explaining them.** That is how a real
#: statement works -- the opening balance already reflects everything before the first line shown --
#: and trying to make the two reconcile would mean seeding balances that drift every time a line is
#: added here.
SEED_TRANSACTIONS = [
    # (account, kind, counterparty, amount_cents, occurred_at)
    ("chequing", TRANSFER, "savings", -12500, "2026-09-02T14:31:07Z"),
    ("savings", TRANSFER, "chequing", 12500, "2026-09-02T14:31:07Z"),
    ("chequing", TRANSFER, "savings", -4000, "2026-09-05T09:12:44Z"),
    ("savings", TRANSFER, "chequing", 4000, "2026-09-05T09:12:44Z"),
]


def _utc_now():
    """When a transaction happened, as an ISO-8601 UTC instant.

    UTC and nothing else. The container's locale is not a fact about when money moved, and a
    timestamp whose meaning depends on where the process happened to be running is not a timestamp
    anybody can query against later.
    """
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


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


@dataclass(frozen=True)
class Transaction:
    """One line of one account's history. Tokens and figures, never prose.

    `amount_cents` is **signed from this account's point of view**: negative is money that left it.
    The caller hears "a transfer of $125.00 to savings" or "$125.00 from chequing", and which of
    those two sentences it is comes from the sign -- composed in the voice agent, like every other
    sentence, never here.

    `counterparty` is the other account's name, or None for a kind that has no other side. Nothing
    produces such a kind today; the column is nullable because a deposit or a fee would be one, and
    forcing a placeholder name into it would be inventing a fact.
    """

    kind: str
    counterparty: str | None
    amount_cents: int
    occurred_at: str


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
        # Same "if empty" rule as the two above, and for the same reason: a restart must not append
        # the demo history a second time to a database that already has it.
        history_seeded = conn.execute("SELECT COUNT(*) FROM transactions").fetchone()[0] > 0
        if not history_seeded:
            conn.executemany(
                "INSERT INTO transactions (account, kind, counterparty, amount_cents, occurred_at) "
                "VALUES (?, ?, ?, ?, ?)",
                SEED_TRANSACTIONS,
            )
        # The one card, active. Same "if empty" rule as everything above -- and here it is what makes
        # "a blocked card resets when the container restarts" true: the filesystem is ephemeral, so a
        # fresh container seeds an active card, while a restart that still has its database keeps the
        # block. Phase 3 settled that behaviour for balances and this inherits it rather than
        # inventing a second story (issue #45).
        card_seeded = conn.execute("SELECT COUNT(*) FROM cards").fetchone()[0] > 0
        if not card_seeded:
            conn.execute(
                "INSERT INTO cards (id, status, blocked_at) VALUES (1, ?, NULL)", (CARD_ACTIVE,)
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


def list_transactions(conn, account, limit=TRANSACTION_LIST_LIMIT):
    """The account's most recent transactions, newest first. Raises UnknownAccount if it does not
    exist.

    **Bounded here, by the service** (issue #44). The caller does not get to ask for more, because
    the caller is a voice channel and the bound is about what can be read aloud rather than about
    what is convenient to send.

    **An account with no transactions returns an empty list.** "Nothing has happened yet" is a normal
    answer from a working system, not an error and not an unknown account -- exactly the distinction
    a declined transfer already keeps against an unknown one.

    Ordered by `occurred_at` then `id`, both descending. `id` is not decoration: the seeded history
    writes two rows sharing one instant, and so does every real transfer, so an order that stopped at
    the timestamp would be unstable between reads.
    """
    _require_account(conn, account)
    with _LOCK:
        rows = conn.execute(
            "SELECT kind, counterparty, amount_cents, occurred_at FROM transactions "
            "WHERE account = ? ORDER BY occurred_at DESC, id DESC LIMIT ?",
            (account, limit),
        ).fetchall()
    return [
        Transaction(kind=kind, counterparty=counterparty, amount_cents=amount, occurred_at=at)
        for kind, counterparty, amount, at in rows
    ]


def _record_transfer(conn, from_account, to_account, amount_cents, occurred_at):
    """The two rows one transfer writes: a debit on the source, a credit on the destination.

    **Called only from inside `transfer`'s `with conn:` block**, so the history and the balances
    commit together or neither does. A history written outside that transaction could survive a
    rollback and tell the caller about money that never moved -- which is the same class of defect as
    computing the resulting balance instead of reading it back.
    """
    conn.executemany(
        "INSERT INTO transactions (account, kind, counterparty, amount_cents, occurred_at) "
        "VALUES (?, ?, ?, ?, ?)",
        [
            (from_account, TRANSFER, to_account, -amount_cents, occurred_at),
            (to_account, TRANSFER, from_account, amount_cents, occurred_at),
        ],
    )


def _require_account(conn, account):
    """Raise UnknownAccount unless the account exists. Named for the raise, because that is the
    whole reason to call it -- `get_balance(conn, x)` on a line that discards the balance reads
    like a no-op someone forgot to delete."""
    get_balance(conn, account)


def transfer(conn, from_account, to_account, amount_cents, now=None):
    """Move money between two accounts. Returns a TransferResult; raises only for bad inputs.

    The outcomes are kept distinct on purpose (CONTEXT.md): an unknown account **raises**, an
    overdrawing transfer is **declined** and mutates nothing, and a valid transfer **completes**
    atomically. A non-positive amount is a malformed request rather than a business decline, so it
    raises too -- the caller has a bug, the account holder has not been refused anything. So is a
    fractional one: cents are whole or they are not cents, and a float reaching an INTEGER column
    is stored REAL, which is the one way a value that is not integer cents can enter persistence.

    **A completed transfer also writes its own history** (issue #44), inside the same transaction as
    the balance updates, so the two can never disagree. **A declined transfer writes nothing** -- a
    decline is a working system saying no, and nothing happened to record.

    `now` is injected for tests, exactly as the circuit breaker's clock is on the other side of the
    seam: a history whose ordering can only be asserted by waiting a second is a history nobody
    tests. It has no production caller.
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
            # Inside the transaction, deliberately: a rollback must take the history with it.
            _record_transfer(
                conn, from_account, to_account, amount_cents,
                _utc_now() if now is None else now,
            )
            from_balance = get_balance(conn, from_account)
            to_balance = get_balance(conn, to_account)
    return TransferResult(
        outcome="completed",
        from_balance_cents=from_balance,
        to_balance_cents=to_balance,
        moved_cents=amount_cents,
    )


def card_status(conn):
    """The profile's card status. Exposed so a test can pin it without reaching for SQL, exactly as
    `credential_digest` is -- there is deliberately no HTTP route for it, because nothing in the
    caller-facing product asks "is my card blocked" except by trying to block it."""
    with _LOCK:
        row = conn.execute("SELECT status FROM cards WHERE id = 1").fetchone()
    return None if row is None else row[0]


def recorded_outcome(conn, idempotency_key):
    """What this key produced last time, or None if it has never been seen.

    Exposed for the same reason `card_status` is: a test that had to infer idempotency from the
    card's status could not tell "the key was recognised" from "the card happened to be blocked
    already", and those are the two behaviours this table exists to keep apart.
    """
    with _LOCK:
        row = conn.execute(
            "SELECT outcome FROM idempotency WHERE key = ?", (idempotency_key,)
        ).fetchone()
    return None if row is None else row[0]


def block_card(conn, idempotency_key, now=None):
    """Block the profile's single card, at most once per key. Returns BLOCKED or ALREADY_BLOCKED.

    **Idempotency is a property of the system of record, not of the client's memory** (issue #45).
    A client that remembered its own keys would forget them the moment its process restarted, and
    the whole reason a key exists is that the client may not be sure its first request landed. So
    the key is stored here, beside the outcome it produced, and a repeat is answered from the record
    rather than re-executed.

    **Two different things can make a second attempt a no-op, and they are kept apart.** A *replayed
    key* is answered with whatever that key produced the first time -- which for the key that did the
    blocking is BLOCKED, so a caller whose request was retried hears the same thing they would have
    heard if it had landed once. A *fresh key against an already-blocked card* is ALREADY_BLOCKED,
    because that is a genuinely new request arriving at a card that is already stopped.

    **Blocking is irreversible here.** There is no unblock, no route to one, and no state transition
    back. A blocked card resets when the container restarts, which is the ephemeral-filesystem
    behaviour Phase 3 settled for balances.

    The read, the check and the two writes are all inside one lock and one transaction, for the
    reason `transfer` spells out: a gap between deciding and acting is a gap two requests can both
    pass through.
    """
    if not isinstance(idempotency_key, str) or not idempotency_key.strip():
        raise ValueError("idempotency key must be a non-empty string")

    with _LOCK:
        replayed = recorded_outcome(conn, idempotency_key)
        if replayed is not None:
            # Answered from the record, without touching the card. This is the branch that makes a
            # retried request safe, and it must not re-execute anything to reach its answer.
            return replayed

        already = card_status(conn) == CARD_BLOCKED
        outcome = ALREADY_BLOCKED if already else BLOCKED
        with conn:
            if not already:
                conn.execute(
                    "UPDATE cards SET status = ?, blocked_at = ? WHERE id = 1",
                    (CARD_BLOCKED, _utc_now() if now is None else now),
                )
            # Recorded whichever way it went, and inside the same transaction as the block itself.
            # Recording only the successful block would mean a replayed ALREADY_BLOCKED key fell
            # through to the status check every time -- which happens to give the same answer today
            # and would stop doing so the moment an unblock existed. The record is the contract.
            conn.execute(
                "INSERT INTO idempotency (key, outcome, recorded_at) VALUES (?, ?, ?)",
                (idempotency_key, outcome, _utc_now() if now is None else now),
            )
    return outcome


def connect(database):
    """Open a connection and ensure the schema and seed exist.

    `check_same_thread=False` because the service is served by an ASGI worker that may touch the
    connection from more than one thread; the workload here is a handful of statements against one
    small table, so a single connection is simpler and entirely sufficient.
    """
    conn = sqlite3.connect(database, check_same_thread=False)
    initialise(conn)
    return conn

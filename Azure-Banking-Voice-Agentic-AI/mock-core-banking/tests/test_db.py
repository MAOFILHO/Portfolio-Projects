"""The system of record's own rules: seeding, balances, and what a transfer is allowed to do.

Money is stored in **integer cents** throughout (issue #26). A service that persists money does
not inherit the demo-grade float the in-memory Phase 1 module used -- these tests assert the type,
not just the value, because the whole point is that no float ever reaches storage.
"""
import contextlib
import sqlite3
import threading
import unittest

from azbank_core_banking import db


def _fresh(test=None):
    """An initialised in-memory database. Seeded, since it starts empty.

    `test` registers a close on teardown -- an unclosed sqlite3 connection is a ResourceWarning,
    and this suite runs with warnings treated as errors.
    """
    conn = sqlite3.connect(":memory:")
    db.initialise(conn)
    if test is not None:
        test.addCleanup(conn.close)
    return conn


class Seeding(unittest.TestCase):
    def test_empty_database_is_seeded(self):
        conn = _fresh(self)
        self.assertEqual(db.list_accounts(conn), {"chequing": 240000, "savings": 50000})

    def test_existing_rows_are_left_alone(self):
        # A restart must not reset balances that are already there. Seeding is "if empty", never
        # "on every boot" -- otherwise a redeploy would silently undo real activity.
        conn = _fresh(self)
        db.transfer(conn, "chequing", "savings", 10000)
        db.initialise(conn)
        self.assertEqual(db.get_balance(conn, "chequing"), 230000)

    def test_seed_values_are_integer_cents_at_the_source(self):
        """Issue #26 criterion 3, asserted where it can actually fail.

        On SEED_ACCOUNTS itself, never on a value read back out of SQLite. Two earlier versions of
        this test did the round trip and neither could fail (/code-review, 2026-09-08 and again on
        8163e83): an INTEGER-affinity column converts a whole float on insert, so a seed of
        240000.0 stores and reads back as int 240000, and `typeof()` reports "integer" for it too.
        Affinity erases the distinction downstream, so the source is the only place it survives --
        and an isinstance check here catches both 2400.00 dollars-as-float and a fractional cent,
        which is everything the round-trip assertions were reaching for.
        """
        for balance in db.SEED_ACCOUNTS.values():
            self.assertIsInstance(balance, int)


class GetBalance(unittest.TestCase):
    def test_known_account(self):
        self.assertEqual(db.get_balance(_fresh(self), "chequing"), 240000)

    def test_unknown_account_raises(self):
        # T-UNKNOWN-ACCT at the system of record. Never a default, never a zero, never another
        # account's balance -- the defect CLAUDE.md's hard exclusions name by example.
        with self.assertRaises(db.UnknownAccount):
            db.get_balance(_fresh(self), "bitcoin")


class Transfer(unittest.TestCase):
    def test_completed_transfer_moves_money(self):
        conn = _fresh(self)
        result = db.transfer(conn, "chequing", "savings", 15000)
        self.assertEqual(result.outcome, "completed")
        self.assertEqual(db.get_balance(conn, "chequing"), 225000)
        self.assertEqual(db.get_balance(conn, "savings"), 65000)

    def test_completed_transfer_reports_the_resulting_balances(self):
        result = db.transfer(_fresh(self), "chequing", "savings", 15000)
        self.assertEqual(result.from_balance_cents, 225000)
        self.assertEqual(result.to_balance_cents, 65000)

    def test_overdrawing_transfer_is_declined_not_raised(self):
        # A declined transfer is a normal outcome of a working system, not an error condition.
        conn = _fresh(self)
        result = db.transfer(conn, "chequing", "savings", 300000)
        self.assertEqual(result.outcome, "declined")
        self.assertEqual(result.reason, "insufficient_funds")
        self.assertEqual(result.available_cents, 240000)

    def test_declined_transfer_mutates_nothing(self):
        conn = _fresh(self)
        db.transfer(conn, "chequing", "savings", 300000)
        self.assertEqual(db.list_accounts(conn), {"chequing": 240000, "savings": 50000})

    def test_unknown_source_account_raises(self):
        with self.assertRaises(db.UnknownAccount):
            db.transfer(_fresh(self), "bitcoin", "savings", 100)

    def test_unknown_destination_account_raises(self):
        with self.assertRaises(db.UnknownAccount):
            db.transfer(_fresh(self), "chequing", "bitcoin", 100)

    def test_non_positive_amount_raises(self):
        for amount in (0, -1):
            with self.assertRaises(ValueError):
                db.transfer(_fresh(self), "chequing", "savings", amount)

    def test_a_fractional_amount_raises(self):
        # Cents are whole or they are not cents. The HTTP route is protected by `amount_cents: int`
        # on TransferRequest, but issue #26 criterion 2 requires this suite to stand on its own
        # without the voice agent, so the rule has to hold at the function too.
        with self.assertRaises(ValueError):
            db.transfer(_fresh(self), "chequing", "savings", 15000.5)

    def test_a_fractional_amount_puts_no_float_in_persistence(self):
        """Issue #26 criterion 3 on the **write** path: "no float appears in persistence".

        The input is the point. An earlier version of this test transferred a whole 15000 and
        asserted `typeof()`, which no arithmetic on INTEGER columns could ever have made REAL, so
        it could not fail; it was then deleted as redundant rather than given an input that bites
        (/code-review, 2026-09-08, twice). 15000.5 is that input: before the guard above, it wrote
        224999.5 and SQLite stored it REAL, because affinity only converts what it can convert
        losslessly.
        """
        conn = _fresh(self)
        with contextlib.suppress(ValueError):
            db.transfer(conn, "chequing", "savings", 15000.5)
        stored = conn.execute("SELECT typeof(balance_cents) FROM accounts").fetchall()
        self.assertEqual([storage_class for (storage_class,) in stored], ["integer", "integer"])

    def test_a_completed_transfer_reports_what_storage_holds(self):
        """The reported balances are read back out of the table, never computed from the amount.

        A self-transfer is the input that tells the two apart, which is why it is the one used
        here: both UPDATEs land on the same row and cancel, so storage still holds 240000 while
        `available - amount_cents` would say 225000. Reporting the arithmetic is how this service
        came to read a caller a balance it had never held (/code-review, 2026-09-08). A transfer
        between two different accounts cannot catch that -- the two agree for every such input.
        """
        conn = _fresh(self)
        result = db.transfer(conn, "chequing", "chequing", 15000)
        self.assertEqual(result.outcome, "completed")
        self.assertEqual(result.from_balance_cents, 240000)
        self.assertEqual(result.to_balance_cents, 240000)
        self.assertEqual(db.get_balance(conn, "chequing"), 240000)

    def test_transfer_of_the_entire_balance_is_allowed(self):
        # The boundary: exactly the available amount is not overdrawing.
        conn = _fresh(self)
        result = db.transfer(conn, "chequing", "savings", 240000)
        self.assertEqual(result.outcome, "completed")
        self.assertEqual(db.get_balance(conn, "chequing"), 0)


class ConcurrentRequests(unittest.TestCase):
    """One connection serves every request, so concurrency is this module's problem, not FastAPI's.

    `build_app` opens a single connection and closes over it, and FastAPI runs `def` routes on a
    threadpool -- so two in-flight transfers really do meet inside these functions. Before the lock
    in db.py they met badly: `with conn:` is per-*connection*, so two requests shared one implicit
    transaction and SQLite answered "cannot start a transaction within a transaction", a SELECT for
    an account that exists came back empty (raising UnknownAccount for "chequing"), and two
    transfers could both pass the sufficiency check and overdraw the account.

    Threads make a test non-deterministic in the red direction only: once serialised the outcome is
    fixed, and before the fix a single round caught the race about a third of the time. ROUNDS is
    sized so that a regression is caught with probability better than 1 - 1e-3 while the whole case
    still runs in well under a second.
    """

    ROUNDS = 20
    THREADS = 4

    def _race_one_round(self):
        """Every thread tries to move the entire balance at once. Returns the outcome labels."""
        conn = sqlite3.connect(":memory:", check_same_thread=False)
        self.addCleanup(conn.close)
        db.initialise(conn)
        ready = threading.Barrier(self.THREADS)
        outcomes, guard = [], threading.Lock()

        def attempt():
            ready.wait()
            try:
                result = db.transfer(conn, "chequing", "savings", 240000)
                label = result.outcome
            except Exception as e:  # noqa: BLE001 - the failure being pinned is "any error at all"
                label = type(e).__name__
            with guard:
                outcomes.append(label)

        workers = [threading.Thread(target=attempt) for _ in range(self.THREADS)]
        for worker in workers:
            worker.start()
        for worker in workers:
            worker.join()
        return outcomes, db.get_balance(conn, "chequing")

    def test_concurrent_transfers_cannot_overdraw_or_corrupt(self):
        for _ in range(self.ROUNDS):
            outcomes, remaining = self._race_one_round()
            self.assertEqual(
                sorted(outcomes), ["completed"] + ["declined"] * (self.THREADS - 1),
                "exactly one transfer of the whole balance may succeed, and the rest are "
                f"ordinary declines -- got {outcomes}",
            )
            self.assertEqual(remaining, 0)


if __name__ == "__main__":
    unittest.main()

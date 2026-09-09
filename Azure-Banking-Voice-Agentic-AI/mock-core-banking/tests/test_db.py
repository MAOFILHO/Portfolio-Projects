"""The system of record's own rules: seeding, balances, and what a transfer is allowed to do.

Money is stored in **integer cents** throughout (issue #26). A service that persists money does
not inherit the demo-grade float the in-memory Phase 1 module used -- these tests assert the type,
not just the value, because the whole point is that no float ever reaches storage.
"""
import contextlib
import sqlite3
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
        # Asserted on SEED_ACCOUNTS itself, never on a value read back out of SQLite. This test
        # used to do the round trip, and it could not fail: an INTEGER-affinity column converts a
        # whole float on insert, so a seed of 240000.0 stores and reads back as int 240000 and an
        # isinstance check downstream cannot tell a float seed from an integer one
        # (/code-review, 2026-09-08 -- issue #26 criterion 3 was passing for the wrong reason).
        for balance in db.SEED_ACCOUNTS.values():
            self.assertIsInstance(balance, int)

    def test_no_balance_is_persisted_as_a_float(self):
        # sqlite3's storage class, which is the one thing affinity cannot paper over: a value it
        # could not convert losslessly -- the fractional cent that dollars-as-float produces --
        # stays REAL and shows up here. Run after a transfer so the arithmetic path is covered
        # too, not just the seed.
        conn = _fresh(self)
        db.transfer(conn, "chequing", "savings", 15000)
        stored = conn.execute("SELECT typeof(balance_cents) FROM accounts").fetchall()
        self.assertEqual([storage_class for (storage_class,) in stored], ["integer", "integer"])


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

    def test_same_account_on_both_sides_raises(self):
        # A malformed request, not a decline: the same reasoning as a non-positive amount. The
        # caller has a bug, and the account holder has not been refused anything.
        with self.assertRaises(ValueError):
            db.transfer(_fresh(self), "chequing", "chequing", 15000)

    def test_same_account_on_both_sides_mutates_nothing(self):
        conn = _fresh(self)
        with contextlib.suppress(ValueError):
            db.transfer(conn, "chequing", "chequing", 15000)
        self.assertEqual(db.list_accounts(conn), {"chequing": 240000, "savings": 50000})

    def test_transfer_of_the_entire_balance_is_allowed(self):
        # The boundary: exactly the available amount is not overdrawing.
        conn = _fresh(self)
        result = db.transfer(conn, "chequing", "savings", 240000)
        self.assertEqual(result.outcome, "completed")
        self.assertEqual(db.get_balance(conn, "chequing"), 0)


if __name__ == "__main__":
    unittest.main()

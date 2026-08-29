import pathlib
import sys
import unittest

# voice-agent/ has a hyphen, so it can't be a normal importable package name yet
# (matches docs/PLAN.md's "Project layout" — not introduced by this test).
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "voice-agent"))

import accounts  # noqa: E402


class ListAccounts(unittest.TestCase):
    def test_returns_starting_balances(self):
        self.assertEqual(accounts.list_accounts(), {"chequing": 2400.0, "savings": 500.0})


class GetBalance(unittest.TestCase):
    def test_valid_account_returns_its_balance(self):
        self.assertEqual(accounts.get_balance("chequing"), 2400.0)

    def test_unknown_account_raises(self):
        # Named hard exclusion (CLAUDE.md): an unknown account must raise, never silently fall
        # back to a made-up balance.
        with self.assertRaises(accounts.UnknownAccountError):
            accounts.get_balance("bitcoin")


class Transfer(unittest.TestCase):
    def setUp(self):
        accounts.ACCOUNTS.clear()
        accounts.ACCOUNTS.update({"chequing": 2400.0, "savings": 500.0})

    def test_sufficient_funds_moves_money_and_speaks_confirmation(self):
        result = accounts.transfer("chequing", "savings", 150.0)
        self.assertEqual(accounts.get_balance("chequing"), 2250.0)
        self.assertEqual(accounts.get_balance("savings"), 650.0)
        self.assertIn("150", result)
        self.assertIn("2250", result)

    def test_insufficient_funds_refuses_without_mutating(self):
        result = accounts.transfer("chequing", "savings", 9999.0)
        self.assertIn("2400", result)  # states the actual available amount
        self.assertEqual(accounts.get_balance("chequing"), 2400.0)  # unchanged
        self.assertEqual(accounts.get_balance("savings"), 500.0)  # unchanged

    def test_unknown_account_raises(self):
        with self.assertRaises(accounts.UnknownAccountError):
            accounts.transfer("chequing", "bitcoin", 50.0)
        with self.assertRaises(accounts.UnknownAccountError):
            accounts.transfer("bitcoin", "chequing", 50.0)

    def test_non_positive_amount_raises(self):
        # A bad argument, not a refusable request — same treatment as an unknown account, not a
        # spoken refusal. Negative would otherwise pass the sufficient-funds check and credit the
        # source account (a reversed transfer); zero is a no-op that shouldn't look like a transfer.
        with self.assertRaises(ValueError):
            accounts.transfer("chequing", "savings", -500.0)
        with self.assertRaises(ValueError):
            accounts.transfer("chequing", "savings", 0.0)
        self.assertEqual(accounts.get_balance("chequing"), 2400.0)  # unchanged
        self.assertEqual(accounts.get_balance("savings"), 500.0)  # unchanged

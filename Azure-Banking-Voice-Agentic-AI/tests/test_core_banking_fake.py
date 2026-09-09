"""The fake's own tests: does it fail the way mock-core-banking fails?

Issue #25's user story 10 -- "I want the fake to satisfy the same protocol as the real client, so
that tests passing against it say something true about production" -- is only worth anything if the
two agree on which error a bad request produces, not merely that *some* error does. Almost every
test in this suite runs against the fake, so a divergence here quietly weakens all of them.

The ordering is the part that drifts. Against the real service a request is validated by
`TransferRequest` **before** the route body runs, so a bad amount is answered by a 422 whether or
not the accounts exist; only then does `db.transfer` look accounts up and raise a 404. A fake that
checks accounts first answers the same request with an unknown-account error, which is a different
outcome in CONTEXT.md's vocabulary and a different sentence to the caller.

`EXPECTED_ERRORS` is the shared table, and **`tests/test_core_banking_live.py` drives the same rows
against a real spawned service** -- so it is not a transcribed constant that stays green while the
service drifts underneath it. This file asserts the fake matches the table; the live test asserts
the service does. Neither claim rests on the other, which is the only arrangement that makes user
story 10 mean anything (/code-review, 2026-09-08, which found the fake answering
`("bitcoin", "savings", -5.0)` with an unknown-account error where production answers malformed,
and applying a sub-cent amount the service would have rejected outright).
"""
import unittest

from azbank_voice_agent.core_banking import CoreBankingRequestError, UnknownAccountError
from azbank_voice_agent.core_banking.fake import FakeCoreBankingClient

#: (from, to, amount) -> the exception the real client raises, for requests that get refused. The
#: rows are ordered to show the precedence: the first four carry an amount the request body rejects,
#: two of them *also* naming an account that does not exist, and all four answer malformed -- so a
#: bad amount outranks an unknown account. The next two are well-formed amounts naming a missing
#: account, which is the only way to reach unknown-account.
#:
#: The last two never reach the wire at all, and that is the point of them: `_cents` refuses an
#: amount that is not a finite number, so the real client and the fake refuse them identically by
#: sharing that one function. `True` is the row that matters -- it is a valid JSON amount, and
#: `True * 100` is an ordinary 100 cents, so db.py's own bool guard at the system of record could
#: never fire on it and a tool call carrying `"amount": true` completed a $1.00 transfer (probe,
#: 2026-09-09).
EXPECTED_ERRORS = [
    (("chequing", "savings", -5.0), CoreBankingRequestError),
    (("bitcoin", "savings", -5.0), CoreBankingRequestError),
    (("bitcoin", "dogecoin", 0.0), CoreBankingRequestError),
    (("chequing", "savings", 0.001), CoreBankingRequestError),
    (("bitcoin", "savings", 100.0), UnknownAccountError),
    (("chequing", "bitcoin", 100.0), UnknownAccountError),
    (("chequing", "savings", "100"), CoreBankingRequestError),
    (("chequing", "savings", True), CoreBankingRequestError),
]


class MatchesTheService(unittest.IsolatedAsyncioTestCase):
    async def test_a_bad_request_raises_what_the_service_would_raise(self):
        for args, expected in EXPECTED_ERRORS:
            with self.subTest(args=args):
                with self.assertRaises(expected):
                    await FakeCoreBankingClient().transfer(*args)

    async def test_a_sub_cent_amount_moves_no_money(self):
        # The service can never see a fraction of a cent: the client rounds dollars to whole cents
        # on the way out and `amount_cents` is an int. The fake used to apply the raw dollars and
        # leave 2399.999 in the account -- a balance the real system could not hold.
        fake = FakeCoreBankingClient()
        with self.assertRaises(CoreBankingRequestError):
            await fake.transfer("chequing", "savings", 0.001)
        self.assertEqual(fake.accounts, {"chequing": 2400.00, "savings": 500.00})

    async def test_an_amount_is_moved_in_whole_cents(self):
        # Rounded the way the real client rounds before sending, so the fake moves what the service
        # would have moved rather than the caller's un-rounded float.
        fake = FakeCoreBankingClient()
        await fake.transfer("chequing", "savings", 0.014)
        self.assertEqual(fake.accounts["savings"], 500.01)


class ReportsWhatItHolds(unittest.IsolatedAsyncioTestCase):
    async def test_a_completed_transfer_reports_its_own_stored_balances(self):
        # The invariant db.transfer is held to, on the input that tells it apart -- see that
        # function for why a self-transfer is the one that does.
        fake = FakeCoreBankingClient()
        result = await fake.transfer("chequing", "chequing", 150.0)
        self.assertEqual(result.from_balance, 2400.00)
        self.assertEqual(result.to_balance, 2400.00)
        self.assertEqual(fake.accounts["chequing"], 2400.00)

    async def test_a_completed_transfer_reports_the_amount_that_actually_moved(self):
        # The dispatcher speaks `moved`, so the fake has to carry it the same way the real client
        # does -- and 2.675 is the input where it differs from the dollars asked for.
        fake = FakeCoreBankingClient()
        result = await fake.transfer("chequing", "savings", 2.675)
        self.assertEqual(result.moved, 2.68)
        self.assertEqual(fake.accounts["savings"], 502.68)


if __name__ == "__main__":
    unittest.main()

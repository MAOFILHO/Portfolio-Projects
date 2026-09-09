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

The expectations below were **measured** against the real service rather than reasoned about --
each row is the status it actually returned, mapped through the client. That matters here more than
usual: the drift these tests pin was introduced by a previous attempt to reason about it
(/code-review, 2026-09-08, which found the fake answering `("bitcoin", "savings", -5.0)` with an
unknown-account error where production answers malformed, and applying a sub-cent amount the
service would have rejected outright).
"""
import unittest

from azbank_voice_agent.core_banking import CoreBankingRequestError, UnknownAccountError
from azbank_voice_agent.core_banking.fake import FakeCoreBankingClient

#: (from, to, amount) -> the exception the real client raises against the real service. A malformed
#: amount outranks an unknown account in every row, because that is the order the service applies.
BAD_REQUESTS = [
    (("chequing", "savings", -5.0), CoreBankingRequestError),
    (("bitcoin", "savings", -5.0), CoreBankingRequestError),
    (("bitcoin", "dogecoin", 0.0), CoreBankingRequestError),
    (("chequing", "savings", 0.001), CoreBankingRequestError),
    (("bitcoin", "savings", 100.0), UnknownAccountError),
    (("chequing", "bitcoin", 100.0), UnknownAccountError),
]


class MatchesTheService(unittest.IsolatedAsyncioTestCase):
    async def test_a_bad_request_raises_what_the_service_would_raise(self):
        for args, expected in BAD_REQUESTS:
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
        # Same invariant the service is held to: the figures come from the balances, never from
        # the arithmetic. A self-transfer is the input that tells those apart.
        fake = FakeCoreBankingClient()
        result = await fake.transfer("chequing", "chequing", 150.0)
        self.assertEqual(result.from_balance, 2400.00)
        self.assertEqual(result.to_balance, 2400.00)
        self.assertEqual(fake.accounts["chequing"], 2400.00)


if __name__ == "__main__":
    unittest.main()

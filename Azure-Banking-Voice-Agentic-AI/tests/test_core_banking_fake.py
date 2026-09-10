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

from azbank_voice_agent.core_banking import (
    CoreBankingRequestError,
    CoreBankingUnavailable,
    UnknownAccountError,
)
from azbank_voice_agent.core_banking.fake import DEFAULT_PIN, FakeCoreBankingClient

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


#: pin -> what `verify_pin` does with it. The same arrangement as EXPECTED_ERRORS above and for the
#: same reason: this file asserts the fake matches the table, tests/test_core_banking_live.py drives
#: the identical rows against a real spawned service, and neither claim rests on the other.
#:
#: Three standings, and the distinction between the last two is the one that matters. An **accepted**
#: and a **rejected credential** are both ordinary results of a working check, told apart by the
#: returned bool rather than by an exception -- a rejection is the system saying no, not failing.
#: Everything else is **unavailable**: no verdict was produced, so none may be inferred. A malformed
#: check is in that bucket rather than its own, because from the authenticator's side a service that
#: refused to answer and a service that could not be reached are the same fact -- see
#: `HttpCoreBankingClient.verify_pin` for why that mapping happens in the client.
EXPECTED_VERIFICATIONS = [
    (DEFAULT_PIN, True),
    ("9999", False),
    ("0000", False),
    ("123", CoreBankingUnavailable),
    ("12345", CoreBankingUnavailable),
    ("abcd", CoreBankingUnavailable),
    ("12 4", CoreBankingUnavailable),
    ("", CoreBankingUnavailable),
    (1234, CoreBankingUnavailable),
    (None, CoreBankingUnavailable),
]


class VerifiesLikeTheService(unittest.IsolatedAsyncioTestCase):
    """The credential store, held to the same table the real service is driven against (issue #35).

    Almost every test in this suite runs against the fake, so a fake that accepted where the service
    rejects would make the whole B1 corpus say something untrue -- and it would say it in the one
    direction that matters, which is the permissive one.
    """

    async def test_the_fake_answers_each_pin_the_way_the_service_does(self):
        for index, (pin, expected) in enumerate(EXPECTED_VERIFICATIONS):
            # By index, never by value: a subTest label is printed on failure.
            with self.subTest(case=index):
                fake = FakeCoreBankingClient()
                if isinstance(expected, type) and issubclass(expected, Exception):
                    with self.assertRaises(expected):
                        await fake.verify_pin(pin)
                else:
                    self.assertIs(await fake.verify_pin(pin), expected)

    async def test_the_store_holds_a_digest_and_not_the_pin(self):
        # Same reasoning as the service's: what is held is what a scan of this object would find.
        fake = FakeCoreBankingClient()
        self.assertNotIn(DEFAULT_PIN, repr(vars(fake)))

    async def test_a_different_credential_can_be_arranged(self):
        # A store rather than a hardcoded answer, so a test can arrange either outcome.
        fake = FakeCoreBankingClient(pin="4321")
        self.assertIs(await fake.verify_pin("4321"), True)
        self.assertIs(await fake.verify_pin(DEFAULT_PIN), False)

    async def test_a_verification_is_recorded_like_every_other_call(self):
        # The fake's call record is the B1 spy (issue #40): a breach is a *banking* method name
        # appearing for a call that never authenticated, so verification has to appear there too or
        # the "exactly one operation is reachable while anonymous" claim has nothing to assert on.
        fake = FakeCoreBankingClient()
        await fake.verify_pin(DEFAULT_PIN)
        self.assertEqual(fake.calls, ["verify_pin"])

    async def test_an_arranged_failure_reaches_verification_too(self):
        # `fail_with` is how the whole-call seam arranges an unreachable backend. A verification
        # that ignored it would make "authentication fails closed when the bank cannot be reached"
        # untestable at the only seam where the caller's experience is visible.
        fake = FakeCoreBankingClient(fail_with=CoreBankingUnavailable("down"))
        with self.assertRaises(CoreBankingUnavailable):
            await fake.verify_pin(DEFAULT_PIN)

    async def test_verification_moves_no_money(self):
        fake = FakeCoreBankingClient()
        await fake.verify_pin(DEFAULT_PIN)
        await fake.verify_pin("9999")
        self.assertEqual(fake.accounts, {"chequing": 2400.00, "savings": 500.00})


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

"""A deterministic stand-in for mock-core-banking.

Satisfies `client.CoreBankingClient` structurally, so the dispatcher cannot tell the difference.
**Nothing in this module makes a network call, ever** -- it holds balances in a dict and applies the
same rules the service applies.

The third of this codebase's pair-with-a-fake modules, after transport/fake.py and realtime/fake.py,
and deliberately shaped like them: a real module rather than a test-local helper, because later
phases extend it rather than rebuild it.

`fail_with` makes the fake fail on demand -- for tests that need a failing backend at the *whole-
call* seam, where what matters is what the caller ends up hearing. The client's own retry and
breaker behaviour is not tested through here; that is tests/test_core_banking_client.py's job,
against httpx.MockTransport.
"""
from .client import CoreBankingRequestError, TransferOutcome, UnknownAccountError

#: Same accounts and balances as the service seeds, in dollars (the units this side of the seam
#: speaks). Cents are the service's business; see client.py's module docstring.
DEFAULT_ACCOUNTS = {"chequing": 2400.00, "savings": 500.00}


class FakeCoreBankingClient:
    """In-memory core banking. Same rules as the real service, no network, no persistence."""

    def __init__(self, accounts=None, fail_with=None):
        self.accounts = dict(DEFAULT_ACCOUNTS if accounts is None else accounts)
        self.fail_with = fail_with
        self.calls = []

    def _check(self, name):
        self.calls.append(name)
        if self.fail_with is not None:
            raise self.fail_with

    async def list_accounts(self):
        self._check("list_accounts")
        return dict(self.accounts)

    async def get_balance(self, account):
        self._check("get_balance")
        if account not in self.accounts:
            raise UnknownAccountError(account)
        return self.accounts[account]

    async def transfer(self, from_account, to_account, amount):
        self._check("transfer")
        # Whole cents, rounded exactly as the real client rounds before sending. The service can
        # never see a fraction of a cent -- `amount_cents` is an int on the wire -- so a fake that
        # applied the raw dollars would move an amount the real system could not, and leave
        # balances like 2399.999 behind (/code-review, 2026-09-08).
        amount = round(amount * 100) / 100

        # Amount before accounts, because that is the order the service applies: `TransferRequest`
        # validates the body before the route body runs, so a bad amount is a 422 whether or not
        # the accounts exist, and only then does the lookup produce a 404. Checking accounts first
        # answered ("bitcoin", "bitcoin", -5) with an unknown-account error where production
        # answers malformed -- a different outcome in CONTEXT.md's vocabulary and a different
        # sentence to the caller. tests/test_core_banking_fake.py pins the order against responses
        # measured from a real spawned service.
        if amount <= 0:
            # CoreBankingRequestError, not ValueError: the real service answers this with a 422,
            # which the real client turns into exactly this type. A fake that failed differently
            # would make tests passing against it say something untrue about production
            # (/code-review, 2026-09-08 -- issue #25's own user story 10).
            raise CoreBankingRequestError(f"transfer amount must be positive, got {amount!r}")
        for account in (from_account, to_account):
            if account not in self.accounts:
                raise UnknownAccountError(account)

        available = self.accounts[from_account]
        if amount > available:
            # Declined, not raised: a normal outcome of a working system (CONTEXT.md).
            return TransferOutcome(
                outcome="declined", reason="insufficient_funds", available=available
            )
        self.accounts[from_account] -= amount
        self.accounts[to_account] += amount
        # Read back out of the dict, never computed -- the same invariant db.transfer is held to.
        # A self-transfer is the input that tells the two apart: both mutations land on one entry
        # and cancel, so anything computed would report a balance nothing holds.
        return TransferOutcome(
            outcome="completed",
            from_balance=self.accounts[from_account],
            to_balance=self.accounts[to_account],
        )

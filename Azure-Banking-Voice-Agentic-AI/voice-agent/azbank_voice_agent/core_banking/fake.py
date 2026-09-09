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
from .client import (
    CoreBankingRequestError,
    TransferOutcome,
    UnknownAccountError,
    _cents,
    _dollars,
)

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
        # Put the amount through the real client's own conversion rather than a second copy of the
        # rounding rule: what the service can actually receive is whatever `_cents` produces, and
        # a fake with its own arithmetic drifts from that silently. Applying the raw dollars left
        # balances like 2399.999 behind, which the real system cannot hold (/code-review,
        # 2026-09-08).
        moved = _dollars(_cents(amount))

        # Amount before accounts, because that is the order the service applies: `TransferRequest`
        # validates the body before the route body runs, so a bad amount is a 422 whether or not
        # the accounts exist, and only then does the lookup produce a 404. See
        # tests/test_core_banking_fake.py, which pins this order against a real spawned service.
        if moved <= 0:
            # CoreBankingRequestError, not ValueError: the real service answers this with a 422,
            # which the real client turns into exactly this type. A fake that failed differently
            # would make tests passing against it say something untrue about production
            # (/code-review, 2026-09-08 -- issue #25's own user story 10). The message quotes the
            # amount as asked for, not as rounded, so a sub-cent request does not report "got 0.0".
            raise CoreBankingRequestError(f"transfer amount must be positive, got {amount!r}")
        for account in (from_account, to_account):
            if account not in self.accounts:
                raise UnknownAccountError(account)

        available = self.accounts[from_account]
        if moved > available:
            # Declined, not raised: a normal outcome of a working system (CONTEXT.md).
            return TransferOutcome(
                outcome="declined", reason="insufficient_funds", available=available
            )
        self.accounts[from_account] -= moved
        self.accounts[to_account] += moved
        # Read back out of the dict, never computed -- the invariant db.transfer is held to, and
        # that function carries the reasoning. `moved` is the amount this fake actually applied,
        # which is what the service reports as `moved_cents`: both are the system of record saying
        # what it did, rather than the client restating what it asked for.
        return TransferOutcome(
            outcome="completed",
            from_balance=self.accounts[from_account],
            to_balance=self.accounts[to_account],
            moved=moved,
        )

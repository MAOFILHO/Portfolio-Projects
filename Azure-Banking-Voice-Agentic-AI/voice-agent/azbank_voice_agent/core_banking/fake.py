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
from .client import TransferOutcome, UnknownAccountError

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
        for account in (from_account, to_account):
            if account not in self.accounts:
                raise UnknownAccountError(account)
        if amount <= 0:
            raise ValueError(f"transfer amount must be positive, got {amount!r}")
        available = self.accounts[from_account]
        if amount > available:
            # Declined, not raised: a normal outcome of a working system (CONTEXT.md).
            return TransferOutcome(
                outcome="declined", reason="insufficient_funds", available=available
            )
        self.accounts[from_account] -= amount
        self.accounts[to_account] += amount
        return TransferOutcome(
            outcome="completed",
            from_balance=self.accounts[from_account],
            to_balance=self.accounts[to_account],
        )

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
import hashlib
import hmac
import re

from .client import (
    CoreBankingRequestError,
    CoreBankingUnavailable,
    TransferOutcome,
    UnknownAccountError,
    _cents,
    _dollars,
)

#: Same accounts and balances as the service seeds, in dollars (the units this side of the seam
#: speaks). Cents are the service's business; see client.py's module docstring.
DEFAULT_ACCOUNTS = {"chequing": 2400.00, "savings": 500.00}

#: The same demo PIN the service seeds. Spelled out again on this side rather than imported,
#: because the two deployables are shared-nothing (docs/PLAN.md decision 9) and this one may not
#: reach into the other's package. A published constant of a prototype, not a secret this file is
#: failing to keep -- B2 forbids the PIN in a transcript, a log line, a span attribute or a
#: persisted record, and source is none of those. The B2 scanner needs a value to search for.
DEFAULT_PIN = "1234"

#: What the service will accept as the shape of a submitted PIN, so the fake refuses what the real
#: service answers 422 to. Kept as the shape rather than a length check, because "four characters"
#: and "four digits" are different rules and only one of them is the service's.
_PIN_SHAPE = re.compile(r"^\d{4}$")


def _digest(pin):
    return hashlib.sha256(pin.encode(errors="replace")).hexdigest()


class FakeCoreBankingClient:
    """In-memory core banking. Same rules as the real service, no network, no persistence."""

    def __init__(self, accounts=None, fail_with=None, pin=None):
        self.accounts = dict(DEFAULT_ACCOUNTS if accounts is None else accounts)
        self.fail_with = fail_with
        # A digest, like the service holds -- not the PIN. A fake that kept the plaintext would be
        # a fake whose own repr could fail B2's scan while the real thing passed it, which is a
        # divergence in exactly the direction that makes a green suite worthless.
        self._pin_digest = _digest(DEFAULT_PIN if pin is None else pin)
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

    async def verify_pin(self, pin):
        """Accepts and refuses on the same rules the service applies, with the same three standings.

        The shape check comes first and answers **unavailable**, because that is what the real
        client reports for the 422 the service would send -- see `HttpCoreBankingClient.verify_pin`
        for why a malformed check is not given a standing of its own. Getting this order or these
        types wrong is the failure mode issue #35 exists to prevent: almost every test in this
        project runs against this object, so a fake that accepted where the service rejects would
        make the whole B1 corpus say something untrue, in the permissive direction.
        """
        self._check("verify_pin")
        if not isinstance(pin, str) or not _PIN_SHAPE.match(pin):
            raise CoreBankingUnavailable("core banking did not answer the credential check")
        return hmac.compare_digest(self._pin_digest, _digest(pin))

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

"""A deterministic stand-in for the call-record store.

Satisfies `store.CallRecordStore` structurally, so the relay cannot tell the difference. **Nothing in
this module makes a network call, ever** -- it holds records in a list.

The fourth of this codebase's pair-with-a-fake modules, after transport/, realtime/ and
core_banking/, and deliberately shaped like them: a real module rather than a test-local helper,
because later phases extend it rather than rebuild it.

`fail_with` makes the store fail on demand. It is what `T-B4-FAILCLOSED` (issue #49) is driven
through, and what proves that a failed escalation record still ends the call (issue #48) -- the two
failure stories this store has, which are deliberately different from each other.
"""
from .store import CallRecordStoreUnavailable


class FakeCallRecordStore:
    """In-memory call records. No network, no persistence, no Azure.

    `escalations` is public, like the core-banking fake's `accounts` is, so a test asserts on what
    was written rather than through a reader method that could itself be wrong.
    """

    def __init__(self, fail_with=None):
        self.fail_with = fail_with
        self.escalations = []
        # Every method that was asked for, in order. The same spy the core-banking fake keeps, and
        # for the same reason: a store that computes perfectly and is never consulted records
        # nothing, and that failure passes every test of what it would have recorded.
        self.calls = []

    def _check(self, name):
        self.calls.append(name)
        if self.fail_with is not None:
            raise self.fail_with

    async def record_escalation(self, record):
        self._check("record_escalation")
        self.escalations.append(record)


def unavailable(message="the call-record store is down"):
    """The failure a test arranges, spelled once so every test arranges the same one.

    Named here rather than written out at each call site: the point of a fail-closed test is that
    *this* exception produces the closed path, and a test that raised its own unrelated type would
    be testing the relay's generic error handling instead.
    """
    return CallRecordStoreUnavailable(message)

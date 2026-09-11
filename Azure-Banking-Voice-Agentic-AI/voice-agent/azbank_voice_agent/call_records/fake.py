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

    def __init__(self, fail_with=None, minutes=None):
        self.fail_with = fail_with
        self.escalations = []
        # day -> minutes spent. Public and pre-loadable, so a test can arrange "today is already
        # spent" without simulating a day's worth of calls.
        self.minutes = dict(minutes or {})
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

    async def minutes_used(self, day):
        """A day nothing has been recorded against is 0.0, exactly as the real client answers.

        The distinction the real client draws between "no row" and "could not read" is the one this
        has to keep: a store that answered 0.0 when it could not read would be a brake that opens
        under the conditions it exists for, and every fail-closed test in the suite runs against
        this object.
        """
        self._check("minutes_used")
        return self.minutes.get(day, 0.0)

    async def record_minutes(self, day, minutes):
        self._check("record_minutes")
        self.minutes[day] = self.minutes.get(day, 0.0) + minutes


def unavailable(message="the call-record store is down"):
    """The failure a test arranges, spelled once so every test arranges the same one.

    Named here rather than written out at each call site: the point of a fail-closed test is that
    *this* exception produces the closed path, and a test that raised its own unrelated type would
    be testing the relay's generic error handling instead.
    """
    return CallRecordStoreUnavailable(message)

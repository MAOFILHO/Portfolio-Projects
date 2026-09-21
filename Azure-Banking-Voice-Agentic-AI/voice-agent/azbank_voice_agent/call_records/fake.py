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
from typing import ClassVar

from .store import CallRecordStoreUnavailable


class FakeCallRecordStore:
    """In-memory call records. No network, no persistence, no Azure.

    `escalations` is public, like the core-banking fake's `accounts` is, so a test asserts on what
    was written rather than through a reader method that could itself be wrong.

    **Every instance registers itself in `WRITTEN`** (issue #53). B2 names *persisted records*, and
    these are the first persisted records the voice agent owns -- but in CI there is no Table
    Storage to scan, so the artifact B2 has to cover is whatever the run's stores actually held. A
    run-wide sweep needs to find them without every test remembering to hand its store over, which
    is the same problem the run-wide log capture solves the same way: collect centrally, scan once,
    at the end.
    """

    #: Every store built during this process, so `tests/test_zz_b2_leak_scan.py` can sweep the lot.
    #: A class attribute rather than a registry object: there is one process, the list is only ever
    #: appended to, and a test run is short. Never read by production code -- nothing constructs
    #: this class outside tests.
    WRITTEN: ClassVar[list] = []

    def __init__(self, fail_with=None, minutes=None):
        FakeCallRecordStore.WRITTEN.append(self)
        self.fail_with = fail_with
        self.escalations = []
        self.call_summaries = []
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

    async def record_call(self, record):
        self._check("record_call")
        # An upsert, like the real store: a call's second write replaces its first in place.
        for i, existing in enumerate(self.call_summaries):
            if existing.correlation_id == record.correlation_id:
                self.call_summaries[i] = record
                return
        self.call_summaries.append(record)

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

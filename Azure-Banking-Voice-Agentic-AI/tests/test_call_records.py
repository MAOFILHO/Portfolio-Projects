"""The call-record store: the fake's rules, and the real client's failure paths (issue #48).

The same two-layer arrangement the core-banking seam uses. The fake's behaviour is asserted directly,
because almost every other test in this project runs against it and a fake that behaved differently
would make a green suite say something untrue. The real client is driven through a mocked table
client, in-process, with no Azure and no network -- exactly as `HttpCoreBankingClient` is driven
through `httpx.MockTransport`.

**What is NOT here is the claim that the store is in the path.** A store that records perfectly and
is never consulted records nothing, and that failure passes every test in this file. That claim is
made at the whole-call seam, in tests/test_whole_call.py, which is the same two-claim structure the
gate's tests use.
"""
import dataclasses
import unittest

from azbank_voice_agent.call_records import (
    REASONS,
    CallRecordStoreUnavailable,
    EscalationRecord,
    EscalationRequested,
    TableStorageCallRecordStore,
)
from azbank_voice_agent.call_records.fake import FakeCallRecordStore, unavailable
from azbank_voice_agent.call_records.store import ESCALATION_PARTITION
from azbank_voice_agent.cost import caps


class TheEscalationRecord(unittest.TestCase):
    def test_it_carries_the_correlation_id_it_was_given(self):
        record = EscalationRecord.now("corr-abc", REASONS[0])
        self.assertEqual(record.correlation_id, "corr-abc")

    def test_the_timestamp_is_utc_and_says_so(self):
        # UTC and nothing else. A record whose meaning depends on where the container happened to be
        # running is not a record anybody can query against later.
        self.assertTrue(EscalationRecord.now("corr-abc", REASONS[0]).occurred_at.endswith("Z"))

    def test_it_is_frozen(self):
        record = EscalationRecord.now("corr-abc", REASONS[0])
        with self.assertRaises(dataclasses.FrozenInstanceError):
            record.reason = "something_else"

    def test_the_reasons_are_a_fixed_set_of_tokens(self):
        # Queryable, not prose (docs/PLAN.md decision 17). A reason with a space in it is a sentence
        # somebody will later try to group by.
        for reason in REASONS:
            with self.subTest(reason=reason):
                self.assertNotIn(" ", reason)
                self.assertEqual(reason, reason.lower())

    def test_nothing_on_the_record_could_hold_a_keyed_digit(self):
        """B2, at the first persisted record the voice agent owns.

        Asserted on the record's fields rather than on one instance: a transcript field, an
        arguments field or a "notes" field added here later is the shape of the leak, and this fails
        the moment one appears rather than when somebody notices.
        """
        self.assertEqual(
            sorted(EscalationRecord.__dataclass_fields__),
            ["correlation_id", "occurred_at", "reason"],
        )


class TheFakeStore(unittest.IsolatedAsyncioTestCase):
    async def test_it_records_what_it_was_given(self):
        store = FakeCallRecordStore()
        record = EscalationRecord.now("corr-abc", REASONS[0])
        await store.record_escalation(record)
        self.assertEqual(store.escalations, [record])

    async def test_it_records_every_call_it_was_asked_for(self):
        store = FakeCallRecordStore()
        await store.record_escalation(EscalationRecord.now("corr-abc", REASONS[0]))
        self.assertEqual(store.calls, ["record_escalation"])

    async def test_an_arranged_failure_raises_the_stores_own_type(self):
        # The type matters: the relay and the dispatcher both branch on it, and a test that arranged
        # some other exception would be testing generic error handling instead.
        store = FakeCallRecordStore(fail_with=unavailable())
        with self.assertRaises(CallRecordStoreUnavailable):
            await store.record_escalation(EscalationRecord.now("corr-abc", REASONS[0]))

    async def test_a_failed_record_is_not_kept(self):
        store = FakeCallRecordStore(fail_with=unavailable())
        with self.assertRaises(CallRecordStoreUnavailable):
            await store.record_escalation(EscalationRecord.now("corr-abc", REASONS[0]))
        self.assertEqual(store.escalations, [])


class _Table:
    """A stand-in for the SDK's async table client. Records what it was handed, or raises."""

    def __init__(self, raises=None):
        self.entities = []
        self.raises = raises
        self.closed = False

    async def create_entity(self, entity):
        if self.raises is not None:
            raise self.raises
        self.entities.append(entity)

    async def close(self):
        self.closed = True


class TheRealClient(unittest.IsolatedAsyncioTestCase):
    """Driven through a mocked table client, the way the core-banking client is driven through
    httpx.MockTransport: every failure path in-process, no sockets, no Azure, no credential."""

    async def test_the_entity_carries_the_records_fields(self):
        table = _Table()
        record = EscalationRecord.now("corr-abc", REASONS[0])
        await TableStorageCallRecordStore(table).record_escalation(record)
        entity = table.entities[0]
        self.assertEqual(entity["correlation_id"], "corr-abc")
        self.assertEqual(entity["reason"], REASONS[0])
        self.assertEqual(entity["occurred_at"], record.occurred_at)

    async def test_records_are_partitioned_by_kind(self):
        table = _Table()
        await TableStorageCallRecordStore(table).record_escalation(
            EscalationRecord.now("corr-abc", REASONS[0])
        )
        self.assertEqual(table.entities[0]["PartitionKey"], ESCALATION_PARTITION)

    async def test_the_row_key_sorts_by_time_and_is_unique_per_call(self):
        table = _Table()
        store = TableStorageCallRecordStore(table)
        first = EscalationRecord(correlation_id="corr-a", reason=REASONS[0],
                                 occurred_at="2026-09-11T10:00:00Z")
        second = EscalationRecord(correlation_id="corr-b", reason=REASONS[0],
                                  occurred_at="2026-09-11T11:00:00Z")
        await store.record_escalation(first)
        await store.record_escalation(second)
        keys = [entity["RowKey"] for entity in table.entities]
        self.assertEqual(keys, sorted(keys))
        self.assertEqual(len(set(keys)), 2)

    async def test_a_row_key_contains_no_character_table_storage_forbids(self):
        table = _Table()
        await TableStorageCallRecordStore(table).record_escalation(
            EscalationRecord.now("corr-abc", REASONS[0])
        )
        for forbidden in ("/", "\\", "#", "?"):
            self.assertNotIn(forbidden, table.entities[0]["RowKey"])

    async def test_any_failure_becomes_the_stores_own_type(self):
        """Whatever the SDK raised, the answer is "the store did not answer".

        Deliberately broad on the client's side: this is a fail-closed boundary for B4's ledger and
        a fail-loud-and-continue one here, and in both cases what matters is that the store did not
        answer -- not which of the SDK's many exception types said so. A narrower catch that missed
        one would put an unhandled error on the relay task, which ends the call.
        """
        for raised in (RuntimeError("boom"), TimeoutError(), ValueError("odd"), OSError("reset")):
            with self.subTest(raised=type(raised).__name__):
                store = TableStorageCallRecordStore(_Table(raises=raised))
                with self.assertRaises(CallRecordStoreUnavailable):
                    await store.record_escalation(EscalationRecord.now("corr-abc", REASONS[0]))

    async def test_the_failure_names_the_cause_without_quoting_it(self):
        # The type is diagnostic and safe; the message could carry anything the SDK chose to put in
        # it, and this is a module whose records B2 now covers.
        store = TableStorageCallRecordStore(_Table(raises=RuntimeError("account key abcd1234")))
        with self.assertRaises(CallRecordStoreUnavailable) as caught:
            await store.record_escalation(EscalationRecord.now("corr-abc", REASONS[0]))
        self.assertIn("RuntimeError", str(caught.exception))
        self.assertNotIn("abcd1234", str(caught.exception))

    async def test_closing_the_store_closes_the_table(self):
        table = _Table()
        await TableStorageCallRecordStore(table).aclose()
        self.assertTrue(table.closed)


class EscalationHasItsOwnType(unittest.TestCase):
    """Three things end a call deliberately now, and they stay distinguishable.

    A cost event, a security event and a routing event. Phase 4 made exactly this argument when
    `AttemptsExhausted` refused to reuse the cost exception; this is the same argument a third time,
    and it is asserted at the types rather than at the behaviour, because the behaviour is identical
    by design -- all three end the call quietly.
    """

    def test_escalation_is_not_a_cost_event(self):
        self.assertFalse(issubclass(EscalationRequested, caps.CallLimitExceeded))
        self.assertFalse(issubclass(caps.CallLimitExceeded, EscalationRequested))

    def test_escalation_is_not_a_security_event(self):
        from azbank_voice_agent.auth import AttemptsExhausted
        self.assertFalse(issubclass(EscalationRequested, AttemptsExhausted))
        self.assertFalse(issubclass(AttemptsExhausted, EscalationRequested))


if __name__ == "__main__":
    unittest.main()

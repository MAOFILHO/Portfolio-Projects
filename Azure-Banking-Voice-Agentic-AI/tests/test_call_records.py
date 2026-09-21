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
import asyncio
import dataclasses
import datetime
import unittest

from azbank_voice_agent.call_records import (
    REASONS,
    CallRecordStoreUnavailable,
    EscalationRecord,
    EscalationRequested,
    TableStorageCallRecordStore,
    is_storable_id,
    storable_or_generated_id,
)
from azbank_voice_agent.call_records.fake import FakeCallRecordStore, unavailable
from azbank_voice_agent.call_records.store import (
    ESCALATION_PARTITION,
    LEDGER_PARTITION,
    LEDGER_TIMEZONE,
    day_key,
)
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


class TheStorableId(unittest.TestCase):
    """A correlation id is a Table RowKey and a Blob name, and it comes from a request header."""

    def test_an_acs_guid_and_the_generated_fallback_are_storable(self):
        self.assertTrue(is_storable_id("0f8fad5b-d9cb-469f-a165-70867728950e"))
        self.assertTrue(is_storable_id("0f8fad5bd9cb469fa16570867728950e"))
        self.assertTrue(is_storable_id("closed-1"))

    def test_characters_a_key_forbids_are_not(self):
        for bad in ("a#b", "a?b", "a/b", "a\\b", "a b", "a\nb", "a..b", "", None, 7):
            self.assertFalse(is_storable_id(bad), repr(bad))

    def test_a_length_the_table_would_refuse_is_not(self):
        self.assertTrue(is_storable_id("x" * 128))
        self.assertFalse(is_storable_id("x" * 129))


if __name__ == "__main__":
    unittest.main()


class _LedgerTable(_Table):
    """A table that can also be read. `get_entity` raises a 404-shaped error when the row is
    absent, which is the shape `azure-data-tables` produces for a missing entity."""

    def __init__(self, rows=None, raises=None, read_raises=None):
        super().__init__(raises=raises)
        self.rows = dict(rows or {})
        self.read_raises = read_raises

    async def get_entity(self, partition_key, row_key):
        if self.read_raises is not None:
            raise self.read_raises
        if row_key not in self.rows:
            raise _NotFound()
        return self.rows[row_key]

    async def upsert_entity(self, entity):
        if self.raises is not None:
            raise self.raises
        self.rows[entity["RowKey"]] = entity
        self.entities.append(entity)


class _NotFound(Exception):
    """Stands in for the SDK's ResourceNotFoundError: an exception carrying `status_code == 404`.

    Matched on the code rather than the type by the module under test, which is what lets that
    module stay importable without the SDK installed.
    """

    status_code = 404


class TheDayLedger(unittest.IsolatedAsyncioTestCase):
    """B4's state, and the distinction the whole brake rests on (issue #49).

    "No row for today" and "I could not read today's row" are different facts. The first is a
    working store answering about a quiet day and must be 0.0; the second is not an answer and must
    raise, because an unknown budget is not permission.
    """

    DAY = "2026-09-11"

    async def test_a_day_with_no_row_is_zero_not_an_error(self):
        # Otherwise the first call of every day would take the closed path -- fail-closed working
        # exactly as specified and completely useless.
        store = TableStorageCallRecordStore(_LedgerTable())
        self.assertEqual(await store.minutes_used(self.DAY), 0.0)

    async def test_a_recorded_day_reports_its_minutes(self):
        table = _LedgerTable(rows={self.DAY: {"PartitionKey": "ledger", "RowKey": self.DAY,
                                              "minutes": 12.5}})
        self.assertEqual(
            await TableStorageCallRecordStore(table).minutes_used(self.DAY), 12.5
        )

    async def test_an_unreadable_store_raises_rather_than_answering_zero(self):
        # The silent-fallback defect applied to the one number B4 depends on. Answering 0.0 here
        # would open the brake under exactly the conditions it exists for.
        store = TableStorageCallRecordStore(_LedgerTable(read_raises=RuntimeError("down")))
        with self.assertRaises(CallRecordStoreUnavailable):
            await store.minutes_used(self.DAY)

    async def test_a_row_missing_its_field_raises_rather_than_answering_zero(self):
        table = _LedgerTable(rows={self.DAY: {"PartitionKey": "ledger", "RowKey": self.DAY}})
        with self.assertRaises(CallRecordStoreUnavailable):
            await TableStorageCallRecordStore(table).minutes_used(self.DAY)

    async def test_a_row_whose_field_is_not_a_number_raises(self):
        table = _LedgerTable(rows={self.DAY: {"minutes": "quite a lot"}})
        with self.assertRaises(CallRecordStoreUnavailable):
            await TableStorageCallRecordStore(table).minutes_used(self.DAY)

    async def test_recording_adds_to_what_was_there(self):
        table = _LedgerTable(rows={self.DAY: {"minutes": 10.0}})
        store = TableStorageCallRecordStore(table)
        await store.record_minutes(self.DAY, 2.5)
        self.assertEqual(await store.minutes_used(self.DAY), 12.5)

    async def test_recording_on_a_fresh_day_starts_from_zero(self):
        store = TableStorageCallRecordStore(_LedgerTable())
        await store.record_minutes(self.DAY, 2.5)
        self.assertEqual(await store.minutes_used(self.DAY), 2.5)

    async def test_the_row_is_keyed_by_the_day_in_the_ledger_partition(self):
        table = _LedgerTable()
        await TableStorageCallRecordStore(table).record_minutes(self.DAY, 1.0)
        self.assertEqual(table.entities[0]["PartitionKey"], LEDGER_PARTITION)
        self.assertEqual(table.entities[0]["RowKey"], self.DAY)

    async def test_two_calls_ending_together_both_count_against_the_day(self):
        """B4 loses no update when two calls end at the same instant.

        **One process is enough.** `record_minutes` awaits a read and then awaits a write, and
        every await is a point the event loop can hand the other call the CPU -- so both read the
        same "before" figure and the second write erases the first. The comment here used to
        answer this by saying the race "needs two replicas, which the Bicep forbids", which was
        wrong twice over: the only `maxReplicas: 1` in `infra/` belongs to mock-core-banking, the
        voice agent has no Bicep module at all, and the in-process interleaving above does not
        care how many replicas there are (/code-review, 2026-09-11).

        It loses updates by *under*-counting, which the module's own comment names as the
        fail-open direction. B4's target is 0 fail-open events.

        The table below yields between read and write, which is what a real round trip does -- it
        does not create the race, it just makes its timing deterministic instead of leaving the
        test to hope for an unlucky schedule.
        """
        class _YieldingLedger(_LedgerTable):
            async def get_entity(self, partition_key, row_key):
                entity = await super().get_entity(partition_key, row_key)
                await asyncio.sleep(0)
                return entity

        store = TableStorageCallRecordStore(_YieldingLedger(rows={self.DAY: {"minutes": 0.0}}))
        await asyncio.gather(
            store.record_minutes(self.DAY, 1.0),
            store.record_minutes(self.DAY, 1.0),
        )
        self.assertEqual(await store.minutes_used(self.DAY), 2.0)

    async def test_a_write_that_fails_raises_rather_than_being_swallowed_here(self):
        # Swallowing belongs to the relay, which knows the call is already over. The client's job is
        # to say what happened.
        store = TableStorageCallRecordStore(_LedgerTable(raises=RuntimeError("down")))
        with self.assertRaises(CallRecordStoreUnavailable):
            await store.record_minutes(self.DAY, 1.0)

    async def test_an_unreadable_ledger_fails_the_write_too(self):
        # `record_minutes` reads before it writes, so an unreadable store cannot produce a write
        # that silently resets the day's total to this call's minutes alone.
        store = TableStorageCallRecordStore(_LedgerTable(read_raises=RuntimeError("down")))
        with self.assertRaises(CallRecordStoreUnavailable):
            await store.record_minutes(self.DAY, 1.0)


class TheDayKey(unittest.TestCase):
    def test_the_timezone_is_written_down_not_inherited(self):
        # The point of the constant: a day boundary that moved with the host's locale would make
        # the ledger, a log line and a query disagree about which day a call belonged to.
        self.assertIs(LEDGER_TIMEZONE, datetime.UTC)

    def test_it_is_a_date_string(self):
        self.assertRegex(day_key(), r"^\d{4}-\d{2}-\d{2}$")


class AGeneratedCorrelationIdCarriesNoDigit(unittest.TestCase):
    """B2's run-wide scan looks for four-digit credentials in every persisted record. A raw
    `uuid4().hex` is more than half digits, so it spells `1234` or `9999` by chance and fails that
    scan about 3 runs in 100 (found by the Phase 8 gate review's own repeated runs). `session.py`
    already keeps its frame and idempotency ids digit-free for the same reason."""

    def test_no_digit_in_any_of_a_thousand_generated_ids(self):
        for _ in range(1000):
            generated = storable_or_generated_id("bad#id?x")
            self.assertFalse(any(c.isdigit() for c in generated), generated)

    def test_a_generated_id_is_still_storable_and_distinct(self):
        ids = {storable_or_generated_id(None) for _ in range(200)}
        self.assertEqual(len(ids), 200)
        self.assertTrue(all(is_storable_id(i) for i in ids))

    def test_an_id_that_is_already_storable_is_kept_as_it_is(self):
        self.assertEqual(storable_or_generated_id("call-1234"), "call-1234")

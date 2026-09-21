"""The call-record store: the protocol, the real client, and what it holds.

**The fourth seam, and the first durable state the voice agent owns.** `core_banking/` talks to the
system of record, which holds money and has never heard of calls. This package holds the things that
are facts about *calls* -- who asked for a person and why, and (issue #49) how many minutes the day
has spent. A system of record that knew about calls would not be a system of record.

Same shape as `core_banking/`, `transport/` and `realtime/`, and deliberately so: a protocol, a real
client, and a fake that satisfies it structurally without a network. The fake is a real module rather
than a test helper, because later phases extend it rather than rebuild it.

**Why not inside mock-core-banking** (docs/phase5/exit-criteria.md, Further Notes). It would have
been free -- that service is being provisioned anyway and needs no new resource. It was rejected
because it would couple B4's brake to the availability of the same service the auth path already
fails closed on: one outage would then both refuse authentication and refuse every call, through two
mechanisms that look independent and are not.

**Authentication is by managed identity.** No connection string, no account key, no shared access
signature -- in this module, in the repo, or in any environment variable this phase adds. That is
consistent with Phase 7's no-keys direction and with how B3's boot guard already reads ARM.

**The role GUID was confirmed live 2026-09-12** against `az role definition list` -- exact match,
BuiltInRole. See `infra/modules/call-records-store.bicep`'s header for the record.

**The async API surface failed on the first real deploy, 2026-09-12, and is fixed.**
`TableServiceClient`'s async pipeline builds an `AioHttpTransport` at construction time regardless
of credential type, importing `aiohttp` to do it -- not a lazy or optional path. The image had never
declared that dependency, so `from_account_url` raised `ModuleNotFoundError` inside `lifespan()` on
every boot, crash-looping the revision before it served a request. Single-revision mode kept the
prior revision serving throughout; no call was ever dropped. Fixed by declaring `aiohttp==3.14.3` in
`voice-agent/pyproject.toml`. **A role assignment returning ARM 200 OK proves creation, not access**
-- criterion 21 of the exit criteria still requires a write that is then read back, which this
failure is what delayed.
"""
import asyncio
import logging
import re
import uuid
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Protocol

log = logging.getLogger("call_records")

#: The table every record in this package lives in. One table, not one per record kind: the records
#: share a resource, a fake, a fail-closed question and an audience, and Table Storage partitions
#: are what keep the kinds apart within it.
TABLE_NAME = "callrecords"

#: The partition each record kind lives under. Named constants rather than inline strings because a
#: partition key typo is a record that is written successfully and can never be found.
ESCALATION_PARTITION = "escalation"
LEDGER_PARTITION = "ledger"
CALL_PARTITION = "call"

#: The timezone "today" means, **written down here rather than inherited from the container's
#: locale** (issue #49). A day boundary that moved with whatever the host happened to be set to
#: would make the ledger, a log line and a query disagree about which day a call belonged to -- and
#: the disagreement would only ever show up as a cap that tripped at the wrong time.
#:
#: UTC, not Eastern, even though the number is Canadian and the caller is not. The ledger is an
#: operational record of what this system spent, not a customer-facing statement, and every other
#: timestamp this project writes is already UTC. One timezone across the whole system beats one that
#: is locally intuitive in one place.
LEDGER_TIMEZONE = UTC

#: The reasons an escalation may carry, and the whole set of them. **A fixed set, not free prose**
#: (docs/PLAN.md decision 17): the record exists so that whoever picks this up can query it, and a
#: reason the model phrased its own way is not queryable. The model picks one of these by name,
#: through the tool's own schema enum.
#:
#: Ordered by how a call actually reaches them, which is also roughly how often they will fire.
REASON_AUTHENTICATION_FAILED = "authentication_failed"
REASON_NOT_UNDERSTOOD = "not_understood"
REASON_UNSUPPORTED_REQUEST = "unsupported_request"
REASON_CALLER_ASKED = "caller_asked"

REASONS = (
    REASON_AUTHENTICATION_FAILED,
    REASON_NOT_UNDERSTOOD,
    REASON_UNSUPPORTED_REQUEST,
    REASON_CALLER_ASKED,
)


class EscalationRequested(Exception):
    """The caller asked for a person, so the call ends.

    **Its own type, not a reuse of `CallLimitExceeded` or `AttemptsExhausted`.** Three different
    things now end a call deliberately -- a cost event, a security event, and a routing event -- and
    they must stay distinguishable in every log and every dashboard that ever reads them. Phase 4
    made exactly this argument when `AttemptsExhausted` refused to reuse the cost exception; this is
    the same argument, a third time.

    It lives in this package rather than in `dispatch/` because it is about the call's ending, and
    because `dispatch/gate.py`'s directory stays short enough to read completely on every review.
    """


class CallRecordStoreUnavailable(RuntimeError):
    """The store could not be reached, or did not answer in a way this client can read.

    One type for every way the store can fail to answer, deliberately. B4's fail-closed rule
    (issue #49) is "an unknown budget never serves a call", and a client that distinguished a
    timeout from a malformed row would invite a caller somewhere to treat one of them as benign.
    Whatever the cause, the answer is not known.
    """


def _is_not_found(error):
    """True for the SDK's "no such entity". Read off the status code rather than the exception type.

    `azure-data-tables` raises `ResourceNotFoundError` for a missing entity, which is an
    `HttpResponseError` carrying `status_code == 404`. Matching on the code rather than importing the
    type keeps this module importable without the SDK -- the same reason the real client's own import
    is lazy -- and a 404 is the thing that actually means "not there" whatever the type is called.
    """
    return getattr(error, "status_code", None) == 404


def _minutes(entity):
    """The minutes on a ledger row, or a refusal to guess.

    A row this client cannot read is not an answer. Returning 0.0 for an unreadable row would be the
    silent-fallback defect CLAUDE.md names by example, applied to the one number B4 depends on --
    and it would fail open, which is the direction that costs money.
    """
    try:
        return float(entity["minutes"])
    except (KeyError, TypeError, ValueError) as e:
        raise CallRecordStoreUnavailable(
            f"the day's ledger row could not be read: {e!r}"
        ) from e


#: What a call's correlation id may contain to be used as a storage key. An allow-list, not a list
#: of bad characters: the id is a Table RowKey (where `/`, `\`, `#`, `?` and control characters are
#: illegal) and a Blob name (where a path separator puts the blob somewhere the container never meant).
#: Capped at 128 characters -- an ACS GUID is 36 -- so a header cannot push a key past what Table
#: Storage accepts (1 KiB for the RowKey, of which the escalation key already spends 21).
_STORABLE_ID = re.compile(r"[A-Za-z0-9._-]{1,128}")


def is_storable_id(correlation_id):
    """Whether an id can key a call's rows and blob. The id arrives from a request header the
    caller's carrier controls, so it is checked where it enters rather than trusted."""
    return (
        isinstance(correlation_id, str)
        and _STORABLE_ID.fullmatch(correlation_id) is not None
        and ".." not in correlation_id
    )


#: The same digit-free translation `realtime/session.py` applies to its frame and idempotency ids.
#: A raw `uuid4().hex` is more than half digits and spells a four-digit run by chance, which B2's
#: run-wide scan reads as a leaked PIN (it failed about 3 runs in 100 until this was applied). Distinct
#: hex strings stay distinct after the translation.
_DIGIT_FREE = str.maketrans("0123456789", "qrstuvwxyz")


def storable_or_generated_id(correlation_id):
    """The id itself if it can key a call's rows, else a fresh, digit-free one. A call that arrives
    with an id no store can hold loses its ACS id, never its row."""
    return correlation_id if is_storable_id(correlation_id) else uuid.uuid4().hex.translate(_DIGIT_FREE)


@dataclass(frozen=True)
class EscalationRecord:
    """One caller who asked for a person, and what the call knew about why.

    `correlation_id` is ACS's own id for the call, handed to the relay rather than fetched by it --
    it is the only value that ties this record to anything else anybody can look up.

    `reason` is one of REASONS above, never prose.

    `occurred_at` is an ISO-8601 UTC instant. UTC and nothing else, for the same reason the system
    of record's timestamps are: a record whose meaning depends on where the container happened to be
    running is not a record anybody can query against later.

    **Nothing here is B2 data and nothing here may become it.** No transcript, no tool arguments, no
    keyed digit -- a reason code and an opaque id. This is the first persisted record the voice agent
    owns, so it is also the first one B2's artifact scan has to cover (issue #53).
    """

    correlation_id: str
    reason: str
    occurred_at: str

    @classmethod
    def now(cls, correlation_id, reason):
        return cls(
            correlation_id=correlation_id,
            reason=reason,
            occurred_at=datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        )


#: The values `CallSummaryRecord.transcript_status` and `.summary_status` may take. Defined beside
#: the record so the pipeline that sets them and the docstring that lists them cannot drift apart.
TRANSCRIPT_STORED = "stored"
TRANSCRIPT_NONE = "none"
TRANSCRIPT_REDACTION_FAILED = "redaction_failed"
TRANSCRIPT_WRITE_FAILED = "write_failed"
SUMMARY_DONE = "done"
SUMMARY_SKIPPED = "skipped"
SUMMARY_FAILED = "failed"
#: Either field, on the row written the moment the call ends and before the slow steps run. A row
#: still saying this when nobody is working on it is a pipeline that started and never finished (the
#: container was killed mid-way); the finished pipeline overwrites it. **It is also what a row says
#: if the final write fails** (the table was unreachable), even when the blob was stored: the row
#: cannot tell a kill from a failed overwrite, and `post-call ... could not record the call summary`
#: in the log is what separates them.
TRANSCRIPT_PENDING = "pending"
SUMMARY_PENDING = "pending"
#: Either field, when the adapter that would have produced it was never configured.
NOT_CONFIGURED = "not_configured"


@dataclass(frozen=True)
class CallSummaryRecord:
    """One finished call: how it ended, and what the post-call pipeline made of it (Phase 8).

    Written after hangup, one per call, keyed by `correlation_id`. `call_outcome` is D10's five-value
    enum and `end_reason` is the raw value it was collapsed from, kept so nothing is lost (D17).

    **B2 covers every field.** The summary and intent are produced from the *redacted* transcript
    only (ADR-007), never the raw one, and the statuses are fixed strings, not prose. No transcript
    text, no keyed digit, no caller phone number belongs here -- `tests/test_zz_b2_leak_scan.py`
    sweeps these records like every other persisted one.

    `transcript_status` is one of the `TRANSCRIPT_*` values or `NOT_CONFIGURED` above, and
    `summary_status` one of the `SUMMARY_*` values or `NOT_CONFIGURED`. Each may be `pending` on the
    first of a call's two writes (see `TRANSCRIPT_PENDING`).
    """

    correlation_id: str
    call_outcome: str
    end_reason: str
    auth_state: str
    turn_count: int
    duration_ms: int
    occurred_at: str
    transcript_status: str
    transcript_blob: str
    summary_status: str
    summary: str
    intent: str


def day_key(now=None):
    """The ledger key for the day `now` falls in: a date, in the stated timezone.

    A date rather than a datetime, because that is what "today's budget" is keyed on, and a string
    rather than a `date`, because it is a partition key on the way out and a log line on the way
    through. `now` is injected so a rollover can be tested instantly rather than over a day.
    """
    moment = datetime.now(LEDGER_TIMEZONE) if now is None else now
    return moment.astimezone(LEDGER_TIMEZONE).date().isoformat()


class CallRecordStore(Protocol):
    """What the relay needs from the call-record store. Satisfied by the real client and the fake.

    Every method is async, for the reason the core-banking protocol gives: the relay is asyncio and a
    synchronous network call on that loop stalls audio in both directions for the whole timeout.
    """

    async def record_escalation(self, record: EscalationRecord) -> None:
        """Append one escalation record. Raises CallRecordStoreUnavailable if it could not.

        **The caller is expected to carry on regardless** (docs/phase5/exit-criteria.md criterion 9).
        Reaching a person matters more than recording that somebody asked to, so a failure here is
        logged loudly and the call still ends with the same apology. This is the one place in the
        phase where the store failing is not fail-closed, and it is deliberate.
        """
        ...

    async def record_call(self, record: CallSummaryRecord) -> None:
        """Write one finished call's summary row. Raises CallRecordStoreUnavailable if it could not.

        Called after hangup by the post-call pipeline, never on the live-call path. A failure is
        logged and dropped by the caller: nothing about a finished call can be made worse by it.
        """
        ...

    async def minutes_used(self, day: str) -> float:
        """How many call minutes `day` has already spent. Raises CallRecordStoreUnavailable.

        **Raising is the whole point.** B4 fails closed, so "I could not read the budget" and "the
        budget is spent" take the same branch and the caller hears the same sentence. A method that
        returned 0.0 when it could not read would be a brake that opens under exactly the conditions
        it exists for.

        A day nothing has been recorded against is **0.0, not an error** -- that is a working store
        answering about a quiet day, which is a different fact from a store that did not answer.
        """
        ...

    async def record_minutes(self, day: str, minutes: float) -> None:
        """Add `minutes` to `day`'s total. Raises CallRecordStoreUnavailable if it could not.

        Called when a call ends, on every path out (issue #50) -- including the paths that raise,
        and including the closed path's own short call. A brake whose usage was invisible in the one
        place it matters would not be a brake anybody could audit.

        **Concurrent calls must not lose each other's minutes.** Part of the contract, not of one
        implementation: two calls ending at the same instant must both count. How an implementer
        gets there is its own business -- `TableStorageCallRecordStore` holds a lock because its
        read and write are separate awaits, and `FakeCallRecordStore` needs nothing because its
        body contains no `await` at all, so the event loop cannot hand another task the CPU part
        way through it. (An earlier version of this sentence said "a single expression", which is
        not true of it -- two statements, neither of them awaiting. The no-await half is the half
        that matters; the count was decoration, and wrong.)
        Stated here because a future implementer reading only the signature would not guess it
        (/code-review, 2026-09-11).
        """
        ...


class TableStorageCallRecordStore:
    """The real client. Azure Table Storage, reached with a managed identity.

    `table_client` is injected so the failure paths can be driven in-process with no network and no
    Azure, exactly as `HttpCoreBankingClient` takes a transport. It has no production caller: the
    classmethod below is what production uses.
    """

    def __init__(self, table_client):
        self._table = table_client
        # Serialises the ledger's read-modify-write; see `record_minutes`. Built here rather than
        # lazily because two calls ending together is exactly when a lazily-built lock would be
        # built twice.
        self._ledger_lock = asyncio.Lock()

    @classmethod
    def from_account_url(cls, account_url, credential):
        """Build against a real Storage account. Imported lazily, deliberately.

        `azure-data-tables` is a runtime dependency of the deployed image and nothing else --
        importing it at module scope would make every test and every tool that merely reads this
        package pay for it, and would make the package unimportable anywhere it is not installed.
        The same reasoning keeps B3's ARM read out of import time.

        **No SDK-level timeout is set here, deliberately.** The bound this seam needs lives in
        `realtime/session.py` (`LEDGER_DEADLINE_SECONDS`), which wraps both the read and the write
        and therefore holds for this client, for the fake, and for anything either is swapped for.
        A transport timeout here would be better still -- it would close the socket rather than
        just stop waiting on it -- but azure-core clients accept unknown keyword arguments and
        ignore them, so a misremembered option name would look configured and do nothing. That is
        the same failure shape as a role assignment returning 200 OK and granting nothing, which
        this phase is already carrying as an open question. `/research` owes the exact option names
        alongside the rest of this module's unverified SDK surface; until then the deadline is at
        the seam, where it is tested (/code-review, 2026-09-11).
        """
        from azure.data.tables.aio import TableServiceClient

        service = TableServiceClient(endpoint=account_url, credential=credential)
        return cls(service.get_table_client(TABLE_NAME))

    async def aclose(self):
        await self._table.close()

    async def minutes_used(self, day):
        try:
            entity = await self._table.get_entity(LEDGER_PARTITION, day)
        except Exception as e:
            if _is_not_found(e):
                # A day nothing has been recorded against. A working store answering about a quiet
                # day -- not a store that failed to answer, and the distinction is what keeps B4
                # from refusing every call on the first call of every day.
                return 0.0
            raise CallRecordStoreUnavailable(
                f"could not read the day's ledger: {type(e).__name__}"
            ) from e
        return _minutes(entity)

    async def record_minutes(self, day, minutes):
        """Add to the day's total, one writer at a time.

        **Read-then-write, not an atomic increment.** Table Storage has no server-side increment,
        so the total is computed here -- and both halves are awaits, which makes the gap between
        them a point the event loop can hand another call the CPU. Two calls ending together would
        otherwise read the same "before" figure and the second write would erase the first,
        *under*-counting the day. B4's own module names undercounting as the fail-open direction
        and B4's target is 0 fail-open events, so this is a brake defect, not a bookkeeping one.

        **An in-process lock, which covers the race that exists.** An earlier version of this
        comment argued no lock was needed because "the race that would lose an update needs two
        replicas, which the Bicep forbids". Both halves were wrong: the only `maxReplicas: 1` in
        `infra/` belongs to mock-core-banking, the voice agent has no Bicep module at all and its
        single replica comes from a provisioning script's flags -- and the interleaving above
        needs one process, not two replicas (/code-review, 2026-09-11).

        **What it does not cover, stated rather than implied**: a second replica, whose two
        processes hold two different locks. That needs optimistic concurrency on the entity's ETag
        with a retry, which is a deliberate not-yet (Marco, 2026-09-11) -- the app runs one replica
        today, and an ETag path cannot be exercised against real Table Storage until the Storage
        account exists. If the scale rule ever changes, this is the line that breaks, and this
        paragraph is what says so.

        **The lock and the relay's deadline interact, and not in the safe direction.**
        `session.LEDGER_DEADLINE_SECONDS` wraps this whole call, lock acquisition included -- so
        under the very contention the lock exists for, a queued writer spends part of its budget
        waiting on the holder's round trip. Run out and `_record_minutes` logs loudly and swallows,
        which undercounts: the fail-open direction again. Deliberately not "fixed" by starting the
        deadline after the lock, which would let teardown block without bound. Not a live risk
        either: one replica serving calls capped at 20 turns cannot queue writers deep enough for
        three seconds of round trips. Written down rather than left to be rediscovered
        (/code-review, 2026-09-11).
        """
        async with self._ledger_lock:
            await self._add_to_day(day, minutes)

    async def _add_to_day(self, day, minutes):
        current = await self.minutes_used(day)
        entity = {
            "PartitionKey": LEDGER_PARTITION,
            "RowKey": day,
            # Rounded on the way in. A ledger holding seventeen significant digits of a float is
            # bad data hygiene on its own, and the precision is meaningless: this is a budget in
            # minutes, and nothing downstream cares past the third decimal. The cap's own arithmetic
            # is unaffected -- the error introduced is under a tenth of a second per call.
            "minutes": round(current + minutes, 3),
        }
        try:
            await self._table.upsert_entity(entity)
        except Exception as e:
            raise CallRecordStoreUnavailable(
                f"could not record the day's minutes: {type(e).__name__}"
            ) from e

    async def record_call(self, record):
        # Upsert, keyed by the call: one row per call, and a retry of the same call's pipeline
        # overwrites its own row rather than adding a second.
        entity = {
            "PartitionKey": CALL_PARTITION,
            "RowKey": record.correlation_id,
            **asdict(record),
        }
        try:
            await self._table.upsert_entity(entity)
        except Exception as e:
            raise CallRecordStoreUnavailable(
                f"could not record a call summary: {type(e).__name__}"
            ) from e

    async def record_escalation(self, record):
        # RowKey is the instant plus the correlation id: unique because no two calls share an id,
        # and sorted by time within the partition because Table Storage orders by RowKey. Neither
        # value can contain a character the key forbids: an ISO instant is digits, dashes, colons
        # and a Z, and the correlation id is checked against `is_storable_id` where it enters
        # (`app.media_stream`), because it comes from a request header rather than from ACS itself.
        entity = {
            "PartitionKey": ESCALATION_PARTITION,
            "RowKey": f"{record.occurred_at}_{record.correlation_id}",
            "correlation_id": record.correlation_id,
            "reason": record.reason,
            "occurred_at": record.occurred_at,
        }
        try:
            await self._table.create_entity(entity)
        except Exception as e:
            # Deliberately broad. This is a fail-closed boundary for #49's ledger and a
            # fail-loud-and-continue one here, and in both cases what matters is that the store did
            # not answer -- not which of the SDK's exception types said so. A narrower catch that
            # missed one would turn "the store is down" into an unhandled error on the relay task,
            # which ends the call. The cause is preserved on the exception for the log.
            raise CallRecordStoreUnavailable(
                f"could not record an escalation: {type(e).__name__}"
            ) from e

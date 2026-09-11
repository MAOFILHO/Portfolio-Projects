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

VERIFY BEFORE THE FIRST DEPLOY (issue #56, and `/research` is the skill for it): the exact
`azure-data-tables` async API surface against the installed version, and the exact name of the
built-in role that grants table data access to a managed identity. Both are written here from the
shape the SDK documents rather than from a live call, and this project has been burned once by an
unverified assumption (`docs/PLAN.md`, decision 12). **A role assignment returning ARM 200 OK proves
creation, not access** -- criterion 21 of the exit criteria requires a write that is then read back.
"""
import logging
from dataclasses import dataclass
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


class TableStorageCallRecordStore:
    """The real client. Azure Table Storage, reached with a managed identity.

    `table_client` is injected so the failure paths can be driven in-process with no network and no
    Azure, exactly as `HttpCoreBankingClient` takes a transport. It has no production caller: the
    classmethod below is what production uses.
    """

    def __init__(self, table_client):
        self._table = table_client

    @classmethod
    def from_account_url(cls, account_url, credential):
        """Build against a real Storage account. Imported lazily, deliberately.

        `azure-data-tables` is a runtime dependency of the deployed image and nothing else --
        importing it at module scope would make every test and every tool that merely reads this
        package pay for it, and would make the package unimportable anywhere it is not installed.
        The same reasoning keeps B3's ARM read out of import time.
        """
        from azure.data.tables.aio import TableServiceClient

        service = TableServiceClient(endpoint=account_url, credential=credential)
        return cls(service.get_table_client(TABLE_NAME))

    async def aclose(self):
        await self._table.close()

    async def record_escalation(self, record):
        # RowKey is the instant plus the correlation id: unique because no two calls share an id,
        # and sorted by time within the partition because Table Storage orders by RowKey. Neither
        # value can contain a character the key forbids -- an ISO instant is digits, dashes, colons
        # and a Z, and ACS correlation ids are hyphenated hex.
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

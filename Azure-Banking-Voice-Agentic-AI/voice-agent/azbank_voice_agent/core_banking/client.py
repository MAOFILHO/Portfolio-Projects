"""Talking to mock-core-banking: the protocol, the real client, and the resilience around it.

This package sits alongside transport/ and realtime/ because it is the same kind of thing they are
-- one external system, its protocol, and (in fake.py) a stand-in that satisfies the same protocol
without a network. Deliberately **not** inside dispatch/: that directory holds gate.py, the file
CLAUDE.md puts a never-auto-accept rule on, and it stays short enough to read completely on every
review.

**Three outcomes, kept distinct** (CONTEXT.md). The whole reason this module exists rather than
`httpx` calls scattered through the dispatcher:

    unknown account   404              -> UnknownAccountError    (raises; T-UNKNOWN-ACCT)
    declined          200 + outcome    -> TransferOutcome        (a normal outcome, not an error)
    unavailable       5xx/timeout/     -> CoreBankingUnavailable (never a balance, ever)
                      refused/open

**Cents on the wire, dollars in the agent.** The service stores and speaks integer cents, because
nothing persisting money should use a float. The model needs a number it can say out loud. That
conversion happens here, once, at the presentation boundary -- and nowhere near persistence.

**Why the numbers below are what they are** (settled at Phase 3 kickoff, issue #25):

  * `TIMEOUT_SECONDS = 1.0` -- generous by roughly two orders of magnitude against a local SQLite
    service, tight enough that a stall is recognised as one rather than heard as a dropped call.
  * `READ_RETRIES = 1`, reads only. **`transfer` is never retried.** It is not idempotent: a POST
    that timed out may already have committed at the service, so a retry can move the money twice.
    A timed-out transfer is reported as unavailable, which is the honest answer -- the outcome
    genuinely is unknown. Idempotency keys are Phase 5's concern, which is why this is a hard rule
    here rather than a tuning parameter.
  * One breaker, per process, for the **whole service**. Not per-endpoint: the failure modes a
    breaker catches here are service-level -- down, saturated, timing out -- and a healthy read
    path must not be able to mask a service that is failing its writes.
"""
import logging
from dataclasses import dataclass
from time import monotonic
from typing import Protocol, runtime_checkable

import httpx

log = logging.getLogger("core_banking")

#: Per-attempt budget: connect plus read. See the module docstring for why 1.0.
TIMEOUT_SECONDS = 1.0

#: Retries for a **read**. Writes get none. Worst case a tool call can add is
#: TIMEOUT_SECONDS * (READ_RETRIES + 1).
READ_RETRIES = 1

#: Consecutive failed *operations* -- not attempts -- before the breaker opens. A read that
#: exhausts its retry is one failure, not two: the operation failed once.
BREAKER_FAILURE_THRESHOLD = 5

#: How long the breaker stays open before allowing a single probe through.
BREAKER_OPEN_SECONDS = 30.0

_CLOSED, _OPEN, _HALF_OPEN = "closed", "open", "half_open"


class UnknownAccountError(LookupError):
    """The named account does not exist at the system of record.

    Raised, never resolved to a default, a zero, or another account's balance. `T-UNKNOWN-ACCT`,
    and the defect CLAUDE.md's hard exclusions name by example -- the reference repo this project
    was seeded from returned a fixed $1,000.00 for any unknown account.
    """


class CoreBankingUnavailable(RuntimeError):
    """mock-core-banking could not be reached, or did not answer in time.

    Distinct from UnknownAccountError on purpose: "that account doesn't exist" and "the bank is
    unreachable" are different facts and get different spoken responses. **Nothing that raises this
    ever also produces a balance figure.**
    """


class CoreBankingRequestError(ValueError):
    """The service rejected the request as malformed -- our bug, not the caller's problem.

    Subclasses ValueError so the dispatcher's existing error handling turns it into a spoken
    error rather than an unhandled exception mid-call.
    """


@dataclass(frozen=True)
class TransferOutcome:
    """What happened to a transfer, in dollars. Two shapes distinguished by `outcome`.

    `completed` carries the resulting balances; `declined` carries the reason and the real amount
    available, so the caller can be told what they *can* do rather than only what they can't.
    """

    outcome: str
    from_balance: float | None = None
    to_balance: float | None = None
    reason: str | None = None
    available: float | None = None


@runtime_checkable
class CoreBankingClient(Protocol):
    """What the dispatcher needs from core banking. Satisfied by the real client and by the fake.

    Every method is async: the relay is asyncio, and a synchronous network call on that loop would
    stall audio in both directions for the full timeout budget (issue #28).
    """

    async def list_accounts(self) -> dict[str, float]:
        ...

    async def get_balance(self, account: str) -> float:
        ...

    async def transfer(self, from_account: str, to_account: str, amount: float) -> TransferOutcome:
        ...


def _dollars(cents):
    return cents / 100


def _cents(dollars):
    """Round rather than truncate: 15000.000000000002 cents is a float artefact of the caller's
    dollars, not an intent to move a fraction of a cent."""
    return round(dollars * 100)


class _CircuitBreaker:
    """Closed -> open after repeated failure -> one half-open probe -> closed or open again.

    The clock is injected so a 30-second open window can be tested without waiting 30 seconds.
    """

    def __init__(self, clock=monotonic):
        self._clock = clock
        self._state = _CLOSED
        self._consecutive_failures = 0
        self._opened_at = 0.0
        self._probe_in_flight = False

    def before_request(self):
        """Raises CoreBankingUnavailable instead of letting a doomed request through."""
        if self._state == _OPEN:
            if self._clock() - self._opened_at < BREAKER_OPEN_SECONDS:
                raise CoreBankingUnavailable(
                    "core banking circuit is open -- not attempting a request"
                )
            # The window has elapsed: let exactly one request through to find out.
            self._state = _HALF_OPEN
            self._probe_in_flight = True
            log.info("core banking circuit half-open: probing")
        elif self._state == _HALF_OPEN and self._probe_in_flight:
            raise CoreBankingUnavailable("core banking circuit is probing -- not piling on")

    def record_success(self):
        if self._state != _CLOSED:
            log.info("core banking circuit closed")
        self._state = _CLOSED
        self._consecutive_failures = 0
        self._probe_in_flight = False

    def record_failure(self):
        was_probing = self._state == _HALF_OPEN
        self._probe_in_flight = False
        if was_probing:
            # The probe failed: straight back to open, with a fresh window.
            self._open()
            return
        self._consecutive_failures += 1
        if self._consecutive_failures >= BREAKER_FAILURE_THRESHOLD:
            self._open()

    def _open(self):
        self._state = _OPEN
        self._opened_at = self._clock()
        log.warning(
            "core banking circuit opened for %ss after %s consecutive failures",
            BREAKER_OPEN_SECONDS, BREAKER_FAILURE_THRESHOLD,
        )


class HttpCoreBankingClient:
    """The real client. Satisfies CoreBankingClient.

    `transport` and `clock` are injected for tests -- httpx.MockTransport produces every failure
    path in-process, with no sockets and no sleeps, and the fake clock makes the breaker's timing
    assertions instant. Neither has a production caller.
    """

    def __init__(self, base_url, transport=None, clock=monotonic):
        self._http = httpx.AsyncClient(
            base_url=base_url,
            timeout=TIMEOUT_SECONDS,
            transport=transport,
        )
        self._breaker = _CircuitBreaker(clock)

    async def aclose(self):
        await self._http.aclose()

    # --- the protocol ---------------------------------------------------------------------------

    async def list_accounts(self):
        payload = await self._get("/accounts")
        return {a["name"]: _dollars(a["balance_cents"]) for a in payload["accounts"]}

    async def get_balance(self, account):
        payload = await self._get(f"/accounts/{account}")
        return _dollars(payload["balance_cents"])

    async def transfer(self, from_account, to_account, amount):
        payload = await self._post("/transfers", {
            "from_account": from_account,
            "to_account": to_account,
            "amount_cents": _cents(amount),
        })
        if payload["outcome"] == "declined":
            return TransferOutcome(
                outcome="declined",
                reason=payload["reason"],
                available=_dollars(payload["available_cents"]),
            )
        return TransferOutcome(
            outcome="completed",
            from_balance=_dollars(payload["from_balance_cents"]),
            to_balance=_dollars(payload["to_balance_cents"]),
        )

    # --- transport ------------------------------------------------------------------------------

    async def _get(self, path):
        return await self._send("GET", path, json=None, attempts=READ_RETRIES + 1)

    async def _post(self, path, body):
        # attempts=1, always. See the module docstring: retrying a non-idempotent write that may
        # already have committed is a double-spend.
        return await self._send("POST", path, json=body, attempts=1)

    async def _send(self, method, path, json, attempts):
        self._breaker.before_request()
        last_error = None
        for attempt in range(attempts):
            try:
                response = await self._http.request(method, path, json=json)
            except httpx.HTTPError as e:
                # Transport-level: timeout, connection refused, DNS. Retryable if this is a read.
                last_error = e
                log.warning("core banking %s %s failed (attempt %s): %s", method, path, attempt + 1, e)
                continue
            if response.status_code >= 500:
                last_error = CoreBankingUnavailable(f"core banking returned {response.status_code}")
                log.warning("core banking %s %s returned %s", method, path, response.status_code)
                continue
            # The service answered. Whatever it said, it is healthy -- a 404 is a working system
            # telling us the account does not exist, so it must not count against the breaker.
            self._breaker.record_success()
            return self._decode(response)

        # Every attempt failed at the transport or with a 5xx: one failed operation, not one per
        # attempt (see BREAKER_FAILURE_THRESHOLD).
        self._breaker.record_failure()
        raise CoreBankingUnavailable(
            f"core banking {method} {path} did not answer: {last_error}"
        ) from last_error

    def _decode(self, response):
        if response.status_code == 404:
            raise UnknownAccountError(str(response.request.url))
        if response.status_code >= 400:
            raise CoreBankingRequestError(
                f"core banking rejected the request with {response.status_code}"
            )
        return response.json()

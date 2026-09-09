"""Talking to mock-core-banking: the protocol, the real client, and the resilience around it.

This package sits alongside transport/ and realtime/ because it is the same kind of thing they are
-- one external system, its protocol, and (in fake.py) a stand-in that satisfies the same protocol
without a network. Deliberately **not** inside dispatch/: that directory holds gate.py, the file
CLAUDE.md puts a never-auto-accept rule on, and it stays short enough to read completely on every
review.

**The outcomes, kept distinct** (CONTEXT.md). The whole reason this module exists rather than
`httpx` calls scattered through the dispatcher:

    malformed         422              -> CoreBankingRequestError (the body was rejected; checked
                                                                   before the accounts are)
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
from math import isfinite
from time import monotonic
from typing import Protocol
from urllib.parse import quote

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
    error rather than an unhandled exception mid-call. **Its message is diagnostic, for logs --
    the dispatcher composes what the caller actually hears** (/code-review, 2026-09-08: the raw
    string "core banking rejected the request with 422" was reaching the caller).
    """


@dataclass(frozen=True)
class TransferOutcome:
    """What happened to a transfer, in dollars. Two shapes distinguished by `outcome`.

    `completed` carries the resulting balances and the amount that actually moved; `declined`
    carries the reason and the real amount available, so the caller can be told what they *can* do
    rather than only what they can't.

    `moved` exists because it is not always the amount that was asked for: dollars become whole
    cents on the way out, and at the half cent the two part company in both directions ($2.675 asked
    for is $2.68 moved, and "%.2f" of the request says $2.67). The caller hears what the system did.
    """

    outcome: str
    from_balance: float | None = None
    to_balance: float | None = None
    moved: float | None = None
    reason: str | None = None
    available: float | None = None


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


def _unknown_account_name(response):
    """The account the service said it could not find, or None if it did not say.

    **Never the request URL.** An earlier version raised UnknownAccountError with the URL, which
    the dispatcher then spoke verbatim -- a caller heard the service's internal hostname read out
    loud (found by /code-review, 2026-09-08). Returns None rather than guessing, so the dispatcher
    can fall back to a sentence that names no account at all.
    """
    try:
        detail = response.json().get("detail")
    except ValueError:
        return None
    return detail.get("account") if isinstance(detail, dict) else None


def _dollars(cents):
    return cents / 100


def _cents(dollars):
    """Dollars to whole cents -- and the boundary that decides what is an amount at all.

    Round rather than truncate: 15000.000000000002 cents is a float artefact of the caller's
    dollars, not an intent to move a fraction of a cent.

    The type check is here, shared by the real client and the fake, because this is the last point
    where an amount is still dollars. db.py has the same rule at the system of record and it could
    never fire: `True * 100` is a perfectly ordinary 100 cents by the time it arrives, so a tool
    call carrying `"amount": true` completed a $1.00 transfer and the agent said "Done" (probe,
    2026-09-09). A string amount was worse -- `round("100")` raises TypeError, which escaped
    `dispatch_tool_call` and ended the call. NaN and Infinity reach here too: json.loads accepts
    both literals.
    """
    if isinstance(dollars, bool) or not isinstance(dollars, (int, float)) or not isfinite(dollars):
        raise CoreBankingRequestError(f"transfer amount must be a finite number, got {dollars!r}")
    return round(dollars * 100)


def _read(payload, build):
    """Interpret a response body, or report the service unavailable.

    A body this client cannot read is not an answer and must never become one. Unread, the missing
    field surfaced as a bare KeyError that the dispatcher spoke to the caller as "'balance_cents'"
    (probe, 2026-09-09). `unavailable` is both the honest outcome -- we did not get a result we
    understand -- and the one branch guaranteed to carry no figure of any kind.
    """
    try:
        return build(payload)
    except (KeyError, TypeError, ValueError) as e:
        raise CoreBankingUnavailable(
            f"core banking returned an unreadable response: {e!r}"
        ) from e


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
        """Raises CoreBankingUnavailable instead of letting a doomed request through.

        Returns True when this call is the half-open probe, so the caller can hold it to a single
        attempt: a probe that quietly retried would put two requests on a backend we already
        believe is sick, and "one half-open probe" would stop being true.
        """
        if self._state == _OPEN:
            if self._clock() - self._opened_at < BREAKER_OPEN_SECONDS:
                raise CoreBankingUnavailable(
                    "core banking circuit is open -- not attempting a request"
                )
            # The window has elapsed: let exactly one request through to find out.
            self._state = _HALF_OPEN
            self._probe_in_flight = True
            log.info("core banking circuit half-open: probing")
            return True
        if self._state == _HALF_OPEN and self._probe_in_flight:
            raise CoreBankingUnavailable("core banking circuit is probing -- not piling on")
        return False

    @property
    def probe_in_flight(self):
        """True while a half-open probe has been let through and has not reported back.

        Read by the client so it can guarantee that one always does. Nothing else clears this flag,
        and the client is process-wide (app.py's lifespan), so a probe that vanished would refuse
        every later call with "circuit is probing" for the life of the process.
        """
        return self._probe_in_flight

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
        return await self._get("/accounts", lambda p: {
            a["name"]: _dollars(a["balance_cents"]) for a in p["accounts"]
        })

    async def get_balance(self, account):
        # Percent-encoded, because the account name is model-supplied text going into a URL path.
        # Interpolated raw it stopped being a name and became routing: "../health" resolved to
        # another route entirely, and "a#b" truncated the path and asked about account "a" -- whose
        # answer the caller was then given by name (probe, 2026-09-09).
        #
        # Encoding does not make a name containing "/" safe, and nothing here pretends it does:
        # uvicorn decodes %2F before the router sees the path, so "chequing%2F" still arrives as a
        # trailing slash and draws a 307 (measured, 2026-09-09). A slash is refused earlier, in the
        # dispatcher, where both clients are held to the same rule.
        return await self._get(
            f"/accounts/{quote(account, safe='')}", lambda p: _dollars(p["balance_cents"])
        )

    async def transfer(self, from_account, to_account, amount):
        def outcome(payload):
            if payload["outcome"] == "declined":
                return TransferOutcome(
                    outcome="declined",
                    reason=payload["reason"],
                    available=_dollars(payload["available_cents"]),
                )
            # `moved_cents` comes from the service, like the balances beside it -- never recomputed
            # here from the dollars that were asked for. The client knows what it sent, but what it
            # sent is not evidence of what was applied, and this figure is spoken to the caller
            # (/code-review, 2026-09-09, spec axis: exit criterion 3's "never computed from the
            # amount" covers every figure in the sentence, not only the balances).
            return TransferOutcome(
                outcome="completed",
                from_balance=_dollars(payload["from_balance_cents"]),
                to_balance=_dollars(payload["to_balance_cents"]),
                moved=_dollars(payload["moved_cents"]),
            )

        return await self._post("/transfers", {
            "from_account": from_account,
            "to_account": to_account,
            "amount_cents": _cents(amount),
        }, outcome)

    # --- transport ------------------------------------------------------------------------------

    async def _get(self, path, build):
        return await self._send("GET", path, json=None, attempts=READ_RETRIES + 1, build=build)

    async def _post(self, path, body, build):
        # attempts=1, always. See the module docstring: retrying a non-idempotent write that may
        # already have committed is a double-spend.
        return await self._send("POST", path, json=body, attempts=1, build=build)

    async def _send(self, method, path, json, attempts, build):
        """One operation: attempts, classification, and the breaker's whole view of it.

        `build` turns the decoded body into the caller's result **inside** this method rather than
        after it returns, and that placement is the point: the breaker may only be told an operation
        succeeded once there is a result to show for it. Recording success first and interpreting
        afterwards meant a service answering redirects, HTML, or a payload missing its fields was
        reported unavailable on every single call while the breaker stayed closed forever -- 20 of
        20 operations reached it, against 10 of 20 for a 5xx (probe, 2026-09-09).
        """
        probing = self._breaker.before_request()
        if probing:
            # The half-open probe is one request, never one-plus-a-retry (#27 AC6). Retrying a
            # probe would double the load on a backend already believed to be sick, and would make
            # "one probe" a claim the code did not actually keep.
            attempts = 1
        last_error = None
        try:
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
                try:
                    result = _read(self._decode(response), build)
                except CoreBankingUnavailable as e:
                    # The service answered, but not with a result: a redirect, a body that is not
                    # JSON, a payload missing its fields. Exactly the standing of a 5xx -- retried
                    # on a read, and one failed operation if every attempt ends here.
                    last_error = e
                    log.warning(
                        "core banking %s %s answered unreadably (attempt %s): %s",
                        method, path, attempt + 1, e,
                    )
                    continue
                except (UnknownAccountError, CoreBankingRequestError):
                    # A working system saying "no such account" or "that request is malformed". It
                    # answered, and coherently, so it is healthy: this must not count against the
                    # breaker, and it must reset a run of failures like any other success.
                    self._breaker.record_success()
                    raise
                self._breaker.record_success()
                return result

            # Every attempt failed at the transport, with a 5xx, or with a response that was not a
            # result: one failed operation, not one per attempt (see BREAKER_FAILURE_THRESHOLD).
            self._breaker.record_failure()
            raise CoreBankingUnavailable(
                f"core banking {method} {path} did not answer: {last_error}"
            ) from last_error
        finally:
            if self._breaker.probe_in_flight:
                # A probe that never reported back. `asyncio.CancelledError` when the caller hangs
                # up mid-probe is the realistic one, and it is not an httpx.HTTPError, so nothing
                # above catches it. The client is process-wide, so leaving the probe marked in
                # flight refused every later call with "circuit is probing" for the life of the
                # process -- a breaker that can never close is worse than no breaker (#27 AC6,
                # user story 20). Counted as a failed probe: the outcome is unknown, and the open
                # window expires on its own.
                self._breaker.record_failure()

    def _decode(self, response):
        if response.status_code == 404:
            raise UnknownAccountError(_unknown_account_name(response))
        if response.status_code >= 400:
            raise CoreBankingRequestError(
                f"core banking rejected the request with {response.status_code}"
            )
        if response.status_code >= 300:
            # Nothing here follows redirects, so a 3xx is not an answer -- and its body is usually
            # empty, which `json()` below then choked on. An ingress in front of the service can
            # produce one without the service changing at all (an HTTPS redirect is the obvious
            # one), so this is a production shape, not a curiosity.
            raise CoreBankingUnavailable(
                f"core banking answered {response.status_code}, which is not a result"
            )
        try:
            return response.json()
        except ValueError as e:
            # An HTML error page from an ingress, or a truncated body. The parser's own message
            # ("Expecting value: line 1 column 1 (char 0)") was reaching the caller's ear (probe,
            # 2026-09-09) -- the same defect /code-review's finding 3 fixed for the 422 wording.
            raise CoreBankingUnavailable("core banking returned a body that is not JSON") from e

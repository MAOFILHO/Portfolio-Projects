"""Answers incoming ACS calls and bridges the media WebSocket to the AOAI realtime deployment.

Handles the Event Grid webhook (subscription-validation handshake + IncomingCall), starts
bidirectional media streaming to /ws with DTMF tones enabled, and hands the accepted WebSocket to
the realtime session module for the whole ACS <-> AOAI relay.

Moved here from docs/echo-app/ in the Phase 2.1 restructure (issue #17) — it is the application
entry point, not documentation, and had been sitting under docs/ since Phase 0.

VERIFY before running: the exact MediaStreamingOptions field/enum names against the installed
azure-communication-callautomation version. Written from docs/PLAN.md's verified protocol facts
(frame shapes, WS URL, EnableBidirectional requirement), not independently re-checked against the
current SDK signature.
"""
import logging
import os
from contextlib import asynccontextmanager

from azure.communication.callautomation import (
    AudioFormat,
    CallAutomationClient,
    MediaStreamingAudioChannelType,
    MediaStreamingContentType,
    MediaStreamingOptions,
    StreamingTransportType,
)
from azure.core.exceptions import AzureError
from azure.identity import DefaultAzureCredential
from fastapi import FastAPI, Request, WebSocket

from .boot import assert_boot_safety, call_records_account_url, core_banking_url
from .call_records import TableStorageCallRecordStore
from .core_banking import HttpCoreBankingClient
from .cost import caps
from .realtime.client import connect_realtime
from .realtime.session import budget_or_closed, run_call, run_closed_call

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
log = logging.getLogger("app")

# Attribution for whatever R-04 measures against this run — baked in at build time by the
# Dockerfile (`pip freeze > /app/installed-versions.txt`, gated by a build-time `test -s`
# assertion so a broken image can't ship), read and logged here so the exact resolved
# dependency graph (transitive included, not just requirements.txt's top-level pins) lives in
# the same log stream as everything else this container reports at boot. The build assertion
# is the real gate against a missing file; this is defense-in-depth for drift after a
# successful build, so a failure here is logged loudly, not swallowed as a bare warning — but
# deliberately doesn't crash the app, since that would burn a deploy on a redundant check.
try:
    with open("/app/installed-versions.txt") as f:
        log.info("boot: resolved package versions:\n%s", f.read())
except OSError as e:
    log.error(
        "boot: ATTRIBUTION BROKEN — /app/installed-versions.txt missing or unreadable (%s). "
        "R-04's measurement from this run has NO recorded dependency graph. The Dockerfile "
        "build assertion should have caught this before the image shipped.",
        e,
    )

#: Where this app answers its own callbacks and media, derived from one variable.
#:
#: **Read at call time, not at import.** Until 2026-09-11 these were four module-level statements
#: running `os.environ[...]` on import, so importing the entry point required an ACS connection
#: string and a base URL, and building a `CallAutomationClient` was an import side effect. Three
#: other modules in this repo state the opposite rule as a rule -- the sibling deployable's entry
#: point ("Importing this module must not open a database"), `boot.py` ("deliberately not at
#: import time") and `realtime/client.py` ("Reads configuration at call time, not import time") --
#: and this was the one file in that role not following it (/code-review, 2026-09-11).
#:
#: No default, same as every other address this project reads: a misconfigured deployment fails
#: where a health check catches it, not mid-call in front of a caller.
def _app_base_url():
    # e.g. https://ca-azbank-echo-p0.<region>.azurecontainerapps.io
    return os.environ["APP_BASE_URL"]


def callback_url():
    return f"{_app_base_url()}/api/callbacks"


def ws_url():
    return _app_base_url().replace("https://", "wss://") + "/ws"


#: The process-wide collaborators, built once in lifespan(). Module-level rather than on app.state
#: so that reading them does not depend on the WebSocket carrying a reference back to its
#: application -- the relay's collaborators are handed in, and this is where they come from.
_core_banking = None
_call_records = None
_call_automation = None


def _process_wide(value, name):
    """A collaborator built in lifespan(), or a loud failure if the app was never started properly.

    **Never lazily constructs one.** A client built on first use would be built *per call*, which is
    exactly the per-call breaker issue #25 (Q13) ruled out -- a breaker thrown away with the call can
    never trip, and a cost store rebuilt per call is a store whose failures nobody accumulates.
    """
    if value is None:
        raise RuntimeError(
            f"{name} is not initialised -- lifespan() did not run. The app must be started through "
            "its ASGI lifespan, not by calling handlers directly."
        )
    return value


def core_banking():
    return _process_wide(_core_banking, "core banking client")


def call_records():
    return _process_wide(_call_records, "call-record store")


def call_automation():
    return _process_wide(_call_automation, "call automation client")


@asynccontextmanager
async def lifespan(_app):
    """B3 runs here, before the first call can arrive -- and deliberately not at import time, so
    that importing this module (tests, tooling) never reaches for ARM.

    It fails closed: if the live deployed model cannot be read, or is not on the allowlist, the
    process exits rather than serving calls on an unapproved model.

    PREREQUISITES FOR A DEPLOY (issue #21): the guard reads ARM, so the Container App needs a
    managed identity with reader access to the Azure OpenAI account, plus AZURE_SUBSCRIPTION_ID,
    AZURE_RESOURCE_GROUP and AOAI_ACCOUNT_NAME in its environment. None of that is provisioned
    today -- until it is, this guard will correctly refuse to start. Verify the ARM leg first with
    `python -m azbank_voice_agent.boot` under `az login`; it is free and read-only.
    """
    global _core_banking, _call_records, _call_automation
    assert_boot_safety()
    # The ACS client, built here for the reason the other two are: startup is where a side effect
    # belongs. Parsing a connection string makes no network call, so this is cheap -- what it buys
    # is that importing this module needs no ACS configuration at all.
    _call_automation = CallAutomationClient.from_connection_string(
        os.environ["ACS_CONNECTION_STRING"]
    )
    # One core-banking client for the life of the process, deliberately -- **not one per call.**
    # The circuit breaker's whole job is to notice the same failure repeating, and a breaker that
    # is thrown away when a call ends can never trip: it would start every call fresh and pay the
    # full timeout budget again on a backend that is known to be down (issue #25, Q13).
    _core_banking = HttpCoreBankingClient(base_url=core_banking_url())
    # The call-record store, likewise once per process and for the same reason (issue #48).
    # **Managed identity, no connection string** -- DefaultAzureCredential picks up the Container
    # App's system-assigned identity, which is the same identity B3's boot guard already uses to
    # read ARM. Nothing here holds an account key.
    _call_records = TableStorageCallRecordStore.from_account_url(
        call_records_account_url(), DefaultAzureCredential()
    )
    try:
        yield
    finally:
        await _core_banking.aclose()
        await _call_records.aclose()
        # Not awaited: the ACS client is the SDK's synchronous one and holds no async resources.
        # It was never closed at all while it lived at module scope; closing it here is what
        # moving it into a lifespan makes possible.
        _call_automation.close()
        _core_banking = None
        _call_records = None
        _call_automation = None


app = FastAPI(lifespan=lifespan)


@app.post("/api/incoming-call")
async def incoming_call(request: Request):
    """Event Grid webhook target. Handles the CloudEvents subscription-validation handshake and,
    on a real IncomingCall event, answers with bidirectional media streaming enabled."""
    events = await request.json()
    for event in events:
        if event.get("eventType") == "Microsoft.EventGrid.SubscriptionValidationEvent":
            code = event["data"]["validationCode"]
            log.info("Event Grid validation handshake, code=%s", code)
            return {"validationResponse": code}
        if event.get("eventType") == "Microsoft.Communication.IncomingCall":
            incoming_call_context = event["data"]["incomingCallContext"]
            correlation_id = event["data"].get("correlationId")
            log.info("IncomingCall, correlationId=%s", correlation_id)
            try:
                call_automation().answer_call(
                    incoming_call_context=incoming_call_context,
                    callback_url=callback_url(),
                    media_streaming=MediaStreamingOptions(
                        transport_url=ws_url(),
                        transport_type=StreamingTransportType.WEBSOCKET,
                        content_type=MediaStreamingContentType.AUDIO,
                        audio_channel_type=MediaStreamingAudioChannelType.MIXED,
                        start_media_streaming=True,
                        enable_bidirectional=True,
                        audio_format=AudioFormat.PCM24_K_MONO,
                        enable_dtmf_tones=True,
                    ),
                )
            except AzureError as e:
                # AzureError, not HttpResponseError: ACS returning an error status (HttpResponseError)
                # is one failure mode, but a transport failure talking to ACS at all -- timeout,
                # connection reset, DNS -- raises ServiceRequestError/ServiceResponseError instead,
                # which are siblings of HttpResponseError under AzureError, not subclasses of it
                # (confirmed against azure-core's exceptions.py). Catching only HttpResponseError
                # would let those escape as an unhandled 500, exactly the bug this fix removes.
                log.error("answer_call failed, correlationId=%s: %s", correlation_id, e)
                # Best-effort, not guaranteed: reject_call reuses the same incoming_call_context, so
                # it only lands if the call is still actually ringing (e.g. answer_call failed on a
                # MediaStreamingOptions config problem). If answer_call failed because the call is
                # already gone -- caller hung up, or the context itself expired -- reject_call hits
                # the same missing/expired resource and fails too (verified against Microsoft's
                # AnswerFailed subcodes 8522/8501/8528 "call not found/not established/terminated"
                # and 71005 "token validation error"). So the caller ends up disconnected when
                # reject_call lands, or was already gone before it ran -- but if reject_call fails
                # for a transient reason (e.g. a network blip) while the call is still actually
                # ringing, the caller is left ringing with no disconnect and no error, same as the
                # original bug minus the 500. No further fallback exists for that case today. The
                # except below only keeps the (expected, logged) reject_call failure from itself
                # propagating as a 500.
                try:
                    call_automation().reject_call(incoming_call_context=incoming_call_context)
                except AzureError as reject_e:
                    log.error("reject_call also failed, correlationId=%s: %s", correlation_id, reject_e)
    return {}


@app.post("/api/callbacks")
async def callbacks(request: Request):
    events = await request.json()
    for event in events:
        log.info("callback event: %s", event.get("type"))
    return {}


@app.websocket("/ws")
async def media_stream(websocket: WebSocket):
    """Opens the realtime connection and hands the whole call to the relay -- ACS media frames
    relay to/from the AOAI realtime deployment. run_call already swallows WebSocketDisconnect
    internally (ends the relay when either side hangs up), so this handler doesn't need its own
    try/except for it.

    This is the only place the real connection is opened; the relay itself takes it as an
    argument (issue #18), which is what lets a whole call run against fakes in CI."""
    correlation_id = websocket.headers.get("x-ms-call-correlation-id")
    connection_id = websocket.headers.get("x-ms-call-connection-id")
    await websocket.accept()
    log.info("WS open correlationId=%s connectionId=%s", correlation_id, connection_id)
    # **B4's daily cap, before anything expensive starts** (issue #49). An exhausted day and an
    # unreadable ledger take the same branch and the caller hears the same sentence -- an unknown
    # budget is not permission. `budget_or_closed`'s own docstring records why this is read here
    # rather than in the incoming-call webhook, which is where the exit criteria placed it.
    try:
        await budget_or_closed(call_records())
    except caps.DailyBudgetSpent:
        async with connect_realtime() as realtime:
            await run_closed_call(websocket, realtime, call_records(), correlation_id)
        log.info("WS closed (service closed) correlationId=%s", correlation_id)
        return
    async with connect_realtime() as realtime:
        # `correlation_id` is handed to the relay rather than fetched by it (issue #48): an
        # escalation record has to carry it, and a relay that reached back through the transport for
        # a header would be a relay that knew what kind of transport it had.
        await run_call(websocket, realtime, core_banking(), call_records(), correlation_id)
    log.info("WS closed correlationId=%s connectionId=%s", correlation_id, connection_id)


@app.get("/healthz")
async def healthz():
    return {"status": "ok"}

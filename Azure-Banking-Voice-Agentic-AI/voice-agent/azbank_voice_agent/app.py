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

from fastapi import FastAPI, Request, WebSocket
from azure.core.exceptions import AzureError
from azure.communication.callautomation import (
    CallAutomationClient,
    MediaStreamingOptions,
    StreamingTransportType,
    MediaStreamingContentType,
    MediaStreamingAudioChannelType,
    AudioFormat,
)

from .boot import assert_boot_safety
from .realtime.client import connect_realtime
from .realtime.session import run_call

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

ACS_CONNECTION_STRING = os.environ["ACS_CONNECTION_STRING"]
APP_BASE_URL = os.environ["APP_BASE_URL"]  # e.g. https://ca-azbank-echo-p0.<region>.azurecontainerapps.io
CALLBACK_URL = f"{APP_BASE_URL}/api/callbacks"
WS_URL = APP_BASE_URL.replace("https://", "wss://") + "/ws"

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
    assert_boot_safety()
    yield


app = FastAPI(lifespan=lifespan)
call_automation_client = CallAutomationClient.from_connection_string(ACS_CONNECTION_STRING)


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
                call_automation_client.answer_call(
                    incoming_call_context=incoming_call_context,
                    callback_url=CALLBACK_URL,
                    media_streaming=MediaStreamingOptions(
                        transport_url=WS_URL,
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
                    call_automation_client.reject_call(incoming_call_context=incoming_call_context)
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
    async with connect_realtime() as realtime:
        await run_call(websocket, realtime)
    log.info("WS closed correlationId=%s connectionId=%s", correlation_id, connection_id)


@app.get("/healthz")
async def healthz():
    return {"status": "ok"}

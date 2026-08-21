"""Phase 0 minimal echo app — NOT production code, exists only to answer calls and measure meters.

Answers an incoming ACS call, starts bidirectional media streaming to /ws, echoes AudioData frames
back verbatim, and logs DtmfData frames with wall-clock timestamps (evidence for R-03: does DTMF
actually arrive during active bidirectional streaming). Also logs per-frame arrival/echo timestamps
for a transport RTT baseline (B5 note in docs/PLAN.md: Phase 0 can only measure transport RTT, not
turn latency — no realtime session exists yet).

VERIFY before running: the exact MediaStreamingOptions field/enum names against the installed
azure-communication-callautomation version. Written from docs/PLAN.md's verified protocol facts
(frame shapes, WS URL, EnableBidirectional requirement), not independently re-checked against the
current SDK signature.
"""
import base64
import json
import logging
import os
import time

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from azure.communication.callautomation import (
    CallAutomationClient,
    MediaStreamingOptions,
    StreamingTransportType,
    MediaStreamingContentType,
    MediaStreamingAudioChannelType,
    AudioFormat,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
log = logging.getLogger("echo")

# --- B2 DELETE-IN-PHASE-2 ---------------------------------------------------------------
# Resolved once at import time, not re-read per-call, so this run's own log stream states up
# front whether raw DTMF tone values could ever appear in it — no need to go hunting for the
# env var separately. Fail-closed: unset, empty, or any unrecognized value all mean OFF.
_LOG_DTMF_RAW = os.environ.get("PHASE0_LOG_DTMF_VALUES", "")
LOG_DTMF_VALUES = _LOG_DTMF_RAW.strip().lower() in ("1", "true", "yes")
log.info(
    "boot: PHASE0_LOG_DTMF_VALUES=%r -> raw DTMF tone values %s be logged this run",
    _LOG_DTMF_RAW or "<unset>", "WILL" if LOG_DTMF_VALUES else "will NOT",
)
# --- END B2 DELETE-IN-PHASE-2 -----------------------------------------------------------

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

app = FastAPI()
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
            log.info("IncomingCall, correlationId=%s", event["data"].get("correlationId"))
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
    return {}


@app.post("/api/callbacks")
async def callbacks(request: Request):
    events = await request.json()
    for event in events:
        log.info("callback event: %s", event.get("type"))
    return {}


@app.websocket("/ws")
async def media_stream(websocket: WebSocket):
    correlation_id = websocket.headers.get("x-ms-call-correlation-id")
    connection_id = websocket.headers.get("x-ms-call-connection-id")
    await websocket.accept()
    stream_start_ts = time.monotonic()  # elapsed-time zero point; time.monotonic() itself is an
                                         # arbitrary epoch, not wall clock or stream-relative
    log.info("WS open correlationId=%s connectionId=%s", correlation_id, connection_id)
    frame_count = 0
    dtmf_count = 0
    try:
        while True:
            raw = await websocket.receive_text()
            recv_ts = time.monotonic()
            msg = json.loads(raw)
            kind = msg.get("kind")

            if kind == "AudioData":
                b64 = msg["audioData"]["data"]
                # Echo verbatim. Outbound keys are capitalized per docs/PLAN.md's verified protocol facts.
                echo = {"Kind": "AudioData", "AudioData": {"Data": b64}}
                await websocket.send_text(json.dumps(echo))
                send_ts = time.monotonic()
                frame_count += 1
                if frame_count % 50 == 0:  # ~once/second at 50 frames/sec
                    log.info(
                        "frame %d echoed, local processing latency=%.1fms",
                        frame_count, (send_ts - recv_ts) * 1000,
                    )

            elif kind == "DtmfData":
                dtmf_count += 1
                # Digit count + arrival timing only — this is the actual R-03 evidence (does DTMF
                # arrive during active bidirectional streaming) and carries no PIN content, so it
                # logs unconditionally, same as the AudioData frame counter above. Elapsed time is
                # relative to WS-open (stream_start_ts), not the raw time.monotonic() value, which
                # is an arbitrary epoch with no meaning on its own.
                log.info(
                    "DTMF digit #%d arrived DURING streaming t=%.3fs since stream start (frame_count so far=%d) — R-03 evidence",
                    dtmf_count, recv_ts - stream_start_ts, frame_count,
                )
                # --- B2 DELETE-IN-PHASE-2 ---------------------------------------------------------
                # Raw tone value, gated on the module-level LOG_DTMF_VALUES resolved once at boot
                # (see top of file) rather than re-reading the env var per digit. Phase 0 has no
                # PIN/auth path, so the value itself carries no confidentiality risk yet — but once
                # Phase 2 puts a PIN on this same DTMF path, B2 (PIN never appears in any
                # transcript/log line/span/record) means this block cannot survive unmodified.
                if LOG_DTMF_VALUES:
                    tone = msg.get("dtmfData", {}).get("data")
                    log.info("DTMF raw tone value=%s (PHASE0_LOG_DTMF_VALUES set)", tone)
                # --- END B2 DELETE-IN-PHASE-2 -----------------------------------------------------

    except WebSocketDisconnect:
        log.info(
            "WS closed correlationId=%s frames=%d dtmf_tones=%d",
            correlation_id, frame_count, dtmf_count,
        )


@app.get("/healthz")
async def healthz():
    return {"status": "ok"}

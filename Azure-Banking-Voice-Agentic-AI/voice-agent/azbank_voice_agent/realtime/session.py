"""Relay one call between a media transport and a realtime connection.

Wire format confirmed live against aoai-azure-banking-voice-cc (gpt-realtime-mini, 2025-10-06,
Canada Central) -- see docs/phase1/research-aoai-realtime-wire-format.md and the two probes that
corrected it (tool-calling support, and the response.output_audio.delta event name). Not re-derived
here.

Issue #18: both collaborators are injected. This module no longer reads the environment or opens a
connection -- `client.connect_realtime()` does that for the real path, and `realtime/fake.py` +
`transport/fake.py` stand in for the whole thing in tests. That is what lets a complete call run in
CI, in milliseconds, with no Azure and no patching.
"""
import asyncio
import logging

from fastapi import WebSocketDisconnect

from ..agents.specs import SYSTEM_PROMPT
from ..cost import caps
from ..dispatch import gate
from ..dispatch.tools import TOOLS, dispatch_tool_call
from ..transport import acs

log = logging.getLogger("bridge")

SESSION_CONFIG = {
    "type": "realtime",
    "instructions": SYSTEM_PROMPT,
    # output_modalities stays audio-only: the SDK's own field docs say audio and text can't both
    # be requested, and audio-only already includes a spoken transcript
    # (response.output_audio_transcript.delta, handled below) -- confirmed live, no need for
    # "text" too.
    "output_modalities": ["audio"],
    "audio": {
        # Set explicitly, not left to defaults: this is a paid call, not the earlier
        # text-modality probe that confirmed these defaults. Values match that confirmed-live
        # default exactly (session.created echo, 2026-08-29).
        "input": {
            "format": {"type": "audio/pcm", "rate": 24000},
            "turn_detection": {
                "type": "server_vad",
                "threshold": 0.5,
                "prefix_padding_ms": 300,
                "silence_duration_ms": 200,
                "create_response": True,
                "interrupt_response": True,
            },
            # input_audio_transcription deliberately omitted: Azure requires the name of an
            # existing transcription-model deployment for this field (not a bare model id like
            # "whisper-1"), and this project has no such deployment -- only gpt-realtime-mini.
            # Provisioning one is a new billable resource, out of scope here.
        },
        "output": {"format": {"type": "audio/pcm", "rate": 24000}},
    },
    "tools": TOOLS,
}


async def run_call(transport, realtime):
    """Relay one call: media transport <-> realtime connection.

    `transport` satisfies transport.protocol.MediaTransport; `realtime` satisfies
    realtime.client.RealtimeConnection. Neither is constructed here.

    No resampling -- both sides are pcm16/24kHz/mono, confirmed live (docs/phase1/
    research-aoai-realtime-wire-format.md). No barge-in, no reconnection: ends when either side
    disconnects, or when a B4 cap trips.
    """
    await realtime.send({"type": "session.update", "session": SESSION_CONFIG})

    # Call-scoped B1 state. Both are fixed for the whole call in Phase 2: there is one agent, and
    # there is no transition into AUTHENTICATED yet. Issue #20 makes `agent` change on handoff;
    # Phase 4 makes `auth_state` change once KBA and the DTMF PIN exist. They are passed to every
    # tool call rather than read from a module global so that a call's authorisation state can
    # never be ambient -- it is always an argument the dispatcher had to be given.
    agent = gate.BANKING_AGENT
    auth_state = gate.ANONYMOUS

    async def transport_to_model():
        while True:
            kind, audio_payload = acs.classify_inbound(await transport.receive_text())
            if kind == acs.DTMF:
                # Arrival only, no raw tone value (B2) -- classify_inbound never returns it.
                # Phase 0's R-03 question (does DTMF arrive during active bidirectional
                # streaming) is already answered, so this doesn't need the elapsed-time-since-
                # stream-start the Phase 0 app's log carried.
                log.info("DTMF frame arrived, ignored by realtime relay (out of scope for Phase 1)")
                continue
            if kind != acs.AUDIO:
                continue  # anything else: out of scope, ignored not crashed on
            await realtime.send({
                "type": "input_audio_buffer.append",
                "audio": audio_payload,
            })

    turn_count = 0

    async def model_to_transport():
        nonlocal turn_count
        async for event in realtime:
            if event.type == "response.output_audio.delta":
                await transport.send_text(acs.outbound_audio_frame(event.delta))
            elif event.type == "response.function_call_arguments.done":
                log.info("tool call: %s(%s)", event.name, event.arguments)
                output = dispatch_tool_call(event.name, event.arguments, agent, auth_state)
                await realtime.send({
                    "type": "conversation.item.create",
                    "item": {
                        "type": "function_call_output",
                        "call_id": event.call_id,
                        "output": output,
                    },
                })
                await realtime.send({"type": "response.create"})
            elif event.type == "response.output_audio_transcript.delta":
                # The only transcript available without provisioning a separate transcription
                # deployment (see the input_audio_transcription comment above) -- what the agent
                # said, not what the caller said.
                log.info("agent said: %s", event.delta)
            elif event.type == "response.done":
                # One full model response cycle = one turn (B4).
                turn_count += 1
                if turn_count >= caps.MAX_CALL_TURNS:
                    log.warning("call hit MAX_CALL_TURNS=%d, ending call (B4)", caps.MAX_CALL_TURNS)
                    raise caps.CallLimitExceeded(f"turn cap ({caps.MAX_CALL_TURNS}) reached")
            elif event.type == "error":
                log.error("AOAI error event: %s", event)

    tasks = [
        asyncio.create_task(transport_to_model()),
        asyncio.create_task(model_to_transport()),
    ]
    done, pending = await asyncio.wait(
        tasks, timeout=caps.MAX_CALL_SECONDS, return_when=asyncio.FIRST_COMPLETED
    )
    for task in pending:
        task.cancel()
    if not done:
        # Timeout fired -- neither side disconnected and no turn cap tripped first (B4).
        log.warning("call hit MAX_CALL_SECONDS=%ds, ending call (B4)", caps.MAX_CALL_SECONDS)
    for task in done:
        exc = task.exception()
        if exc is not None and not isinstance(exc, (WebSocketDisconnect, caps.CallLimitExceeded)):
            raise exc
    log.info("call ended")

"""Relay between ACS media streaming and the AOAI realtime deployment.

Wire format confirmed live against aoai-azure-banking-voice-cc (gpt-realtime-mini, 2025-10-06,
Canada Central) -- see docs/phase1/research-aoai-realtime-wire-format.md and the two probes that
corrected it (tool-calling support, and the response.output_audio.delta event name). Not re-derived
here.

Phase 2.1 restructure (issue #17): the tool table, the cost caps, the prompt, and the ACS frame
shapes moved to their own modules; what stays here is the session configuration and the relay
itself. Behaviour is unchanged. Issue #18 makes the transport and the realtime client injectable
so a whole call can run against fakes with no patching -- today this still constructs its own
client from the environment.
"""
import asyncio
import logging
import os

from fastapi import WebSocketDisconnect
from openai import AsyncOpenAI

from ..agents.specs import SYSTEM_PROMPT
from ..cost import caps
from ..dispatch.tools import TOOLS, dispatch_tool_call
from ..transport import acs

log = logging.getLogger("bridge")


async def run_bridge(acs_ws):
    """Relay one call: ACS media WebSocket <-> AOAI realtime WebSocket.

    No resampling -- both sides are pcm16/24kHz/mono, confirmed live (docs/phase1/
    research-aoai-realtime-wire-format.md). No barge-in, no reconnection: ends when either side
    disconnects, or when a B4 cap trips.
    """
    api_key = os.environ["AOAI_KEY"]
    endpoint = os.environ["AOAI_ENDPOINT"]
    # No default: matches AOAI_KEY/AOAI_ENDPOINT above, and fails closed on a missing pin rather
    # than silently falling back to some other deployment (B3, CLAUDE.md) -- a pin rotation is
    # then a config change in 01-provision.sh, not an edit here. The boot-time (name, version)
    # guard that makes B3 real is issue #21's deliverable.
    deployment = os.environ["AOAI_DEPLOYMENT"]
    base_url = endpoint.replace("https://", "wss://").rstrip("/") + "/openai/v1"
    client = AsyncOpenAI(api_key=api_key, websocket_base_url=base_url)

    async with client.realtime.connect(model=deployment) as aoai:
        await aoai.send({
            "type": "session.update",
            "session": {
                "type": "realtime",
                "instructions": SYSTEM_PROMPT,
                # output_modalities stays audio-only: the SDK's own field docs say audio and text
                # can't both be requested, and audio-only already includes a spoken transcript
                # (response.output_audio_transcript.delta, handled below) -- confirmed live, no
                # need for "text" too.
                "output_modalities": ["audio"],
                "audio": {
                    # Set explicitly, not left to defaults: this is a paid call, not the earlier
                    # text-modality probe that confirmed these defaults. Values match that
                    # confirmed-live default exactly (session.created echo, 2026-08-29).
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
                        # input_audio_transcription deliberately omitted: Azure requires the name
                        # of an existing transcription-model deployment for this field (not a
                        # bare model id like "whisper-1"), and this project has no such deployment
                        # -- only gpt-realtime-mini. Provisioning one is a new billable resource,
                        # out of scope here.
                    },
                    "output": {"format": {"type": "audio/pcm", "rate": 24000}},
                },
                "tools": TOOLS,
            },
        })

        async def acs_to_aoai():
            while True:
                kind, audio_payload = acs.classify_inbound(await acs_ws.receive_text())
                if kind == acs.DTMF:
                    # Arrival only, no raw tone value (B2) -- classify_inbound never returns it.
                    # Phase 0's R-03 question (does DTMF arrive during active bidirectional
                    # streaming) is already answered, so this doesn't need the elapsed-time-since-
                    # stream-start the Phase 0 app's log carried.
                    log.info("DTMF frame arrived, ignored by realtime relay (out of scope for Phase 1)")
                    continue
                if kind != acs.AUDIO:
                    continue  # anything else: out of scope, ignored not crashed on
                await aoai.send({
                    "type": "input_audio_buffer.append",
                    "audio": audio_payload,
                })

        turn_count = 0

        async def aoai_to_acs():
            nonlocal turn_count
            async for event in aoai:
                if event.type == "response.output_audio.delta":
                    await acs_ws.send_text(acs.outbound_audio_frame(event.delta))
                elif event.type == "response.function_call_arguments.done":
                    log.info("tool call: %s(%s)", event.name, event.arguments)
                    output = dispatch_tool_call(event.name, event.arguments)
                    await aoai.send({
                        "type": "conversation.item.create",
                        "item": {
                            "type": "function_call_output",
                            "call_id": event.call_id,
                            "output": output,
                        },
                    })
                    await aoai.send({"type": "response.create"})
                elif event.type == "response.output_audio_transcript.delta":
                    # The only transcript available without provisioning a separate transcription
                    # deployment (see the input_audio_transcription comment above) -- what the
                    # agent said, not what the caller said.
                    log.info("agent said: %s", event.delta)
                elif event.type == "response.done":
                    # One full model response cycle = one turn (B4).
                    turn_count += 1
                    if turn_count >= caps.MAX_CALL_TURNS:
                        log.warning(
                            "call hit MAX_CALL_TURNS=%d, ending call (B4)", caps.MAX_CALL_TURNS
                        )
                        raise caps.CallLimitExceeded(f"turn cap ({caps.MAX_CALL_TURNS}) reached")
                elif event.type == "error":
                    log.error("AOAI error event: %s", event)

        tasks = [asyncio.create_task(acs_to_aoai()), asyncio.create_task(aoai_to_acs())]
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
            if exc is not None and not isinstance(
                exc, (WebSocketDisconnect, caps.CallLimitExceeded)
            ):
                raise exc
    log.info("call ended")

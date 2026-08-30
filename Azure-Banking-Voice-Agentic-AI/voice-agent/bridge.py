"""Phase 1 relay between ACS media streaming and the AOAI realtime deployment.

Wire format confirmed live against aoai-azure-banking-voice-cc (gpt-realtime-mini, 2025-10-06,
Canada Central) -- see docs/phase1/research-aoai-realtime-wire-format.md and the two probes that
corrected it (tool-calling support, and the response.output_audio.delta event name). Not re-derived
here.
"""
import asyncio
import json
import logging
import os

from fastapi import WebSocketDisconnect
from openai import AsyncOpenAI

import accounts

log = logging.getLogger("bridge")

DEPLOYMENT = "gpt-realtime-mini"  # deployment name; model version pinned server-side, see B3

SYSTEM_PROMPT = (
    "You are a phone banking agent. Be brief and clear, like a real phone call. Always use the "
    "tools to check a balance or make a transfer -- never state a balance or confirm a transfer "
    "without calling the matching tool first. If a transfer can't go through, say why and state "
    "the actual available amount."
)

_ACCOUNT_ENUM = {"type": "string", "enum": list(accounts.ACCOUNTS)}

TOOLS = [
    {
        "type": "function",
        "name": "get_balance",
        "description": "Get the current balance of one of the caller's accounts.",
        "parameters": {
            "type": "object",
            "properties": {"account": _ACCOUNT_ENUM},
            "required": ["account"],
        },
    },
    {
        "type": "function",
        "name": "transfer",
        "description": "Transfer money between the caller's accounts.",
        "parameters": {
            "type": "object",
            "properties": {
                "from_account": _ACCOUNT_ENUM,
                "to_account": _ACCOUNT_ENUM,
                "amount": {"type": "number"},
            },
            "required": ["from_account", "to_account", "amount"],
        },
    },
    {
        "type": "function",
        "name": "list_accounts",
        "description": "List the caller's accounts.",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
]

_DISPATCH = {
    "get_balance": lambda args: accounts.get_balance(args["account"]),
    "transfer": lambda args: accounts.transfer(
        args["from_account"], args["to_account"], args["amount"]
    ),
    "list_accounts": lambda args: accounts.list_accounts(),
}


def dispatch_tool_call(name, arguments_json):
    """Run one tool call, returning the JSON string for a function_call_output. Never raises --
    an unknown tool name, a missing argument, or an accounts.py error (bad account, non-positive
    amount) all come back as {"error": "..."} so the model can say something sensible instead of
    the call going silent."""
    try:
        args = json.loads(arguments_json) if arguments_json else {}
        result = _DISPATCH[name](args)
    except (KeyError, ValueError) as e:
        return json.dumps({"error": str(e) or f"unknown tool: {name}"})
    return json.dumps({"result": result})


async def run_bridge(acs_ws):
    """Relay one call: ACS media WebSocket <-> AOAI realtime WebSocket.

    No resampling -- both sides are pcm16/24kHz/mono, confirmed live (docs/phase1/
    research-aoai-realtime-wire-format.md). turn_detection and audio format are left unset:
    the deployment's own defaults are already server_vad and audio/pcm@24000, confirmed live via
    the session.created echo in this project's probe -- no need to restate them. No barge-in, no
    reconnection: ends when either side disconnects.
    """
    api_key = os.environ["AOAI_KEY"]
    endpoint = os.environ["AOAI_ENDPOINT"]
    base_url = endpoint.replace("https://", "wss://").rstrip("/") + "/openai/v1"
    client = AsyncOpenAI(api_key=api_key, websocket_base_url=base_url)

    async with client.realtime.connect(model=DEPLOYMENT) as aoai:
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
                raw = await acs_ws.receive_text()
                msg = json.loads(raw)
                # Inbound keys are lowercase ("kind"/"audioData"/"data"), outbound keys are
                # capitalized ("Kind"/"AudioData"/"Data") -- a real, verified ACS asymmetry, not a
                # bug: docs/PLAN.md's "Key protocol facts (verified)" states it explicitly, and
                # docs/echo-app/app.py uses exactly this casing on both sides in the code that
                # answered and echoed all 3 real Phase 0 test calls.
                if msg.get("kind") != "AudioData":
                    continue  # DtmfData etc: out of scope for Phase 1, ignored not crashed on
                await aoai.send({
                    "type": "input_audio_buffer.append",
                    "audio": msg["audioData"]["data"],
                })

        async def aoai_to_acs():
            async for event in aoai:
                if event.type == "response.output_audio.delta":
                    await acs_ws.send_text(json.dumps(
                        {"Kind": "AudioData", "AudioData": {"Data": event.delta}}
                    ))
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
                elif event.type == "error":
                    log.error("AOAI error event: %s", event)

        tasks = [asyncio.create_task(acs_to_aoai()), asyncio.create_task(aoai_to_acs())]
        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for task in pending:
            task.cancel()
        for task in done:
            exc = task.exception()
            if exc is not None and not isinstance(exc, WebSocketDisconnect):
                raise exc
    log.info("call ended")

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
import json
import logging

from fastapi import WebSocketDisconnect

from .. import auth
from ..agents import specs
from ..cost import caps
from ..dispatch import gate
from ..dispatch.tools import dispatch_tool_call
from ..transport import acs

log = logging.getLogger("bridge")

# Set explicitly, not left to defaults: this is a paid call, not the earlier text-modality probe
# that confirmed these defaults. Values match that confirmed-live default exactly (session.created
# echo, 2026-08-29). Shared by every agent's session.update -- only instructions and tools change
# on a handoff (issue #20), never the audio wire shape.
_AUDIO_CONFIG = {
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
        # input_audio_transcription deliberately omitted: Azure requires the name of an existing
        # transcription-model deployment for this field (not a bare model id like "whisper-1"),
        # and this project has no such deployment -- only gpt-realtime-mini. Provisioning one is a
        # new billable resource, out of scope here.
    },
    "output": {"format": {"type": "audio/pcm", "rate": 24000}},
}


def _spoken_note(text):
    """A conversation item that tells the caller something the model did not decide.

    The same two-message mechanism a handoff uses -- an item followed by a response request -- but
    a plain message rather than a `function_call_output`, because no tool call is being answered.

    **This item shape is not verified against the live deployment.** Phase 1 confirmed the
    `function_call_output` shape on a real call (docs/phase1/research-aoai-realtime-wire-format.md);
    this one is the documented shape and nothing more, because Phase 4 deploys nothing and makes no
    real call. It sits in the same known-partial as the keyed tone itself and closes at the same
    point: Phase 5's real-call exit.

    The text is composed in auth/, never here and never in the system of record, and it states the
    outcome only -- never a digit, never an attempt count.
    """
    return {
        "type": "conversation.item.create",
        "item": {
            "type": "message",
            "role": "system",
            "content": [{"type": "input_text", "text": text}],
        },
    }


def _session_update(identity):
    """The session.update message for handing (or opening) the call to `identity` -- instructions
    and tools come from agents/specs.py's AgentSpec table; everything else about the wire shape is
    fixed. Reconfigures the one existing session; issue #20's handoff never opens a second one."""
    spec = specs.AGENTS[identity]
    return {
        "type": "session.update",
        "session": {
            "type": "realtime",
            "instructions": spec.instructions,
            # output_modalities stays audio-only: the SDK's own field docs say audio and text
            # can't both be requested, and audio-only already includes a spoken transcript
            # (response.output_audio_transcript.delta, handled below) -- confirmed live, no need
            # for "text" too.
            "output_modalities": ["audio"],
            "audio": _AUDIO_CONFIG,
            "tools": specs.tools_for(identity),
        },
    }


async def run_call(transport, realtime, core_banking):
    """Relay one call: media transport <-> realtime connection, with core banking behind the gate.

    `transport` satisfies transport.protocol.MediaTransport; `realtime` satisfies
    realtime.client.RealtimeConnection; `core_banking` satisfies core_banking.CoreBankingClient.
    None of the three is constructed here -- that is what lets a whole call run against fakes with
    no patching (issue #18, extended to the third collaborator by issue #28).

    No resampling -- both sides are pcm16/24kHz/mono, confirmed live (docs/phase1/
    research-aoai-realtime-wire-format.md). No barge-in, no reconnection: ends when either side
    disconnects, or when a B4 cap trips.
    """
    # Call-scoped B1 state. `agent` starts on TRIAGE and changes on handoff (issue #20,
    # model_to_transport below). `auth_state` starts ANONYMOUS and flips exactly once, when the
    # authenticator reports a passed PIN check (issue #37) -- it is never set from anywhere else
    # and there is no path back. Both are passed to every tool call rather than read from a module
    # global so that a call's authorisation state can never be ambient: it is always an argument
    # the dispatcher had to be given.
    agent = gate.TRIAGE_AGENT
    auth_state = gate.ANONYMOUS

    # One per call, holding this caller's keypad and their attempts. Constructed here because this
    # is where the call's auth state already lives, and given the same core-banking client the
    # dispatcher gets -- which is what makes an unreachable service fail authentication closed
    # without a second fail-closed path (issue #35).
    authenticator = auth.Authenticator(core_banking)

    await realtime.send(_session_update(agent))

    async def transport_to_model():
        nonlocal auth_state
        while True:
            kind, payload = acs.classify_inbound(await transport.receive_text())
            if kind == acs.DTMF:
                # Arrival, then outcome. Never the digit and never how many have arrived (B2): the
                # tone value goes straight from the classifier into the authenticator and is not
                # held anywhere in between. Phase 0's R-03 question -- does DTMF arrive during
                # active bidirectional streaming -- is already answered, so this does not need the
                # elapsed-time-since-stream-start the Phase 0 app's log carried.
                log.info("DTMF frame arrived")
                outcome = await authenticator.key(payload)
                log.info("PIN entry outcome: %s", outcome)
                if authenticator.is_authenticated:
                    # The one write. Idempotent by construction -- the machine's transition is
                    # one-way, so a later key press cannot bring this back round a second time.
                    auth_state = gate.AUTHENTICATED
                sentence = auth.sentence_for(outcome)
                if sentence is not None:
                    # Told, not left in silence -- the same reason a refusal is spoken rather than
                    # met with nothing. The three silent outcomes are the caller still keying, and
                    # speaking over them is the one thing a PIN prompt cannot afford to do.
                    await realtime.send(_spoken_note(sentence))
                    await realtime.send({"type": "response.create"})
                if outcome == auth.outcomes.EXHAUSTED:
                    log.warning("PIN attempts exhausted, ending call")
                    raise auth.AttemptsExhausted("three rejected credentials")
                continue
            if kind != acs.AUDIO:
                continue  # anything else: out of scope, ignored not crashed on
            await realtime.send({
                "type": "input_audio_buffer.append",
                "audio": payload,
            })

    turn_count = 0

    async def model_to_transport():
        nonlocal turn_count, agent
        # B5 latency anchors (arrival only, no audio/content -- B2): "caller turn ended" pairs
        # with the *next* "agent audio started" to give a real round-trip turn latency, tool
        # round-trips included -- a tool-call-only response has no audio, so response.done resets
        # this flag below without a fresh "caller turn ended" in between, and the eventual audio
        # after the round-trip still measures against the real turn boundary. Added 2026-09-08:
        # Call 1's real logs had tool-call and handoff events but no timestamp pair to compute
        # turn latency from at all.
        audio_started = False
        async for event in realtime:
            if event.type == "response.output_audio.delta":
                if not audio_started:
                    audio_started = True
                    log.info("agent audio started")
                await transport.send_text(acs.outbound_audio_frame(event.delta))
            elif event.type == "input_audio_buffer.speech_stopped":
                # Server VAD's turn-ended signal -- confirmed live 2026-09-08, see
                # realtime/fake.py's speech_stopped().
                log.info("caller turn ended")
            elif event.type == "response.function_call_arguments.done":
                # `agent` (not just event.name) matters here: handoff_target() checks the edge
                # against the *calling* agent's own declared handoff_to, so a target that exists
                # but isn't an edge this agent declares comes back None and falls through to the
                # branch below -- an ordinary dispatch_tool_call, refused by the gate the same as
                # any other unrecognised tool name (fixed 2026-09-07, /code-review of #20: this
                # used to check only "does the target agent exist", not "did this agent declare
                # this edge").
                handoff_target = specs.handoff_target(event.name, agent)
                if handoff_target is not None:
                    # A handoff is routing, not a banking tool -- it never reaches
                    # dispatch_tool_call or the gate (dispatch/gate.py's own docstring: agent
                    # tool-scoping is defence in depth, not the control). Agent identities are
                    # not sensitive (B2) -- safe to log which one the call moved to.
                    log.info("handoff: %s -> %s", agent, handoff_target)
                    agent = handoff_target
                    await realtime.send({
                        "type": "conversation.item.create",
                        "item": {
                            "type": "function_call_output",
                            "call_id": event.call_id,
                            "output": json.dumps({"result": f"transferred to {agent}"}),
                        },
                    })
                    # Reconfigures the one existing session -- never opens a second one (issue
                    # #20's acceptance criterion).
                    await realtime.send(_session_update(agent))
                    await realtime.send({"type": "response.create"})
                    continue
                # Tool name only, never the arguments (B2): they can carry account identifiers
                # today, and Phase 4 puts PIN-adjacent data on this exact path --
                # dispatch_tool_call's own docstring already promises not to log arguments; this
                # relay must not undercut that a frame earlier.
                log.info("tool call: %s", event.name)
                # Awaited since Phase 3 (issue #28): this now does real network I/O against
                # mock-core-banking. Calling it synchronously would block this event loop for the
                # client's whole timeout budget -- audio would stop being relayed in both
                # directions and barge-in would stop working while it waited.
                output = await dispatch_tool_call(
                    event.name, event.arguments, agent, auth_state, core_banking=core_banking
                )
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
                # said, not what the caller said. Arrival only, never the words (B2): the moment
                # the agent can ever repeat something sensitive back, this is the log line that
                # would carry it, so no content lands here now either -- no exception carved out
                # for Phase 2 just because there's nothing sensitive to say yet.
                log.info("agent transcript delta received (%d chars)", len(event.delta))
            elif event.type == "response.done":
                # One full model response cycle = one turn (B4).
                audio_started = False  # B5: next audio delta is a new response cycle's first.
                turn_count += 1
                if turn_count >= caps.MAX_CALL_TURNS:
                    log.warning("call hit MAX_CALL_TURNS=%d, ending call (B4)", caps.MAX_CALL_TURNS)
                    raise caps.CallLimitExceeded(f"turn cap ({caps.MAX_CALL_TURNS}) reached")
            elif event.type == "error":
                # Arrival only, never event content (B2): this project has never observed a real
                # error event live (docs/phase1/research-aoai-realtime-wire-format.md -- "zero
                # error events end to end"), so no field of it is verified safe to log. A
                # validation error can echo the offending request back in its message (e.g. bad
                # tool arguments), which is exactly the content B2 forbids -- the earlier fix to
                # the tool-call and transcript lines above missed this one because it logged the
                # whole event object, not a field (caught by /code-review, 2026-09-07). Detailed,
                # redaction-aware error observability is Phase 6's job, not Phase 2's.
                log.error("AOAI error event received")

    tasks = [
        asyncio.create_task(transport_to_model()),
        asyncio.create_task(model_to_transport()),
    ]
    try:
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
            # Expected ways a call ends, not relay failures: the caller hung up, a B4 cap tripped,
            # or the caller ran out of PIN attempts. AttemptsExhausted travels this same branch
            # with its own type rather than reusing CallLimitExceeded, so a security event and a
            # cost event stay distinguishable in every log that ever reads them.
            expected = (WebSocketDisconnect, caps.CallLimitExceeded, auth.AttemptsExhausted)
            if exc is not None and not isinstance(exc, expected):
                raise exc
    finally:
        # The third point the buffer is zeroed at, after submit and clear -- on call end, whatever
        # the outcome. In a finally because "whatever the outcome" includes the paths that raise.
        authenticator.end_call()
    log.info("call ended")

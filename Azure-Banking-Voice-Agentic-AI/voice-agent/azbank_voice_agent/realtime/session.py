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
import collections
import json
import logging
import uuid

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


def _spoken_note(text, event_id):
    """A conversation item that tells the caller something the model did not decide.

    The same two-message mechanism a handoff uses -- an item followed by a response request -- but
    a plain message rather than a `function_call_output`, because no tool call is being answered.

    **The shape is confirmed against the specification** (`docs/phase4/research-carried-findings.md`
    §1b-1c, researched 2026-09-10 against the OpenAI realtime types generated at the SDK version
    this project pins). `role: "system"` with `type: "message"` is one of exactly three message
    items the `ConversationItem` union accepts, `input_text` is not merely permitted on a system
    message but is the *only* permitted content type there, and the spec's own docstring names this
    use case: "system messages can be added at any point in the conversation… for smaller updates".
    Azure's realtime reference delegates wholesale to that specification and documents exactly one
    deviation, which touches `input_audio_transcription` and nothing here.

    **What remains unverified is acceptance, not shape.** No primary source states that Azure's GA
    endpoint accepts this item, and none documents `conversation.item.create` per model version --
    which is the case B3 exists for, since one deployment name has already been seen to span
    versions that behave differently. Phase 1 hit the same wall on a different event and settled it
    with a one-frame live probe; that is what closes this, at Phase 5's real-call exit.

    **`event_id` is what makes that probe readable.** A rejection arrives as an `error` event whose
    `error.event_id` names the client frame that caused it -- the only documented way to attribute
    one. Stamping an id here turns "an error arrived" into "*this* injection was refused". The id
    is generated, never derived from anything the caller keyed.

    The text is composed in auth/, never here and never in the system of record, and it states the
    outcome only -- never a digit, never an attempt count.
    """
    return {
        "type": "conversation.item.create",
        "event_id": event_id,
        "item": {
            "type": "message",
            "role": "system",
            "content": [{"type": "input_text", "text": text}],
        },
    }


#: Decimal digits mapped to letters outside the hex alphabet. **Bijective**, so an id built through
#: it is unique exactly as often as the uuid behind it: `a`-`f` are untouched and `q`-`z` are not
#: hex, so no two distinct hex strings can collide after translation.
_DIGIT_FREE = str.maketrans("0123456789", "qrstuvwxyz")


def _new_event_id():
    """An id for one frame the relay sends: unique, opaque, and carrying no decimal digit at all.

    Named for a frame rather than an item because both halves of the injection mechanism carry one
    -- the item and the response request that makes it speak.

    **The digit-free part is not decoration.** A raw `uuid4().hex` is 32 characters drawn from an
    alphabet that is more than half digits, so across a call's injections it will eventually spell
    some four-digit run by chance -- and B2's run-wide scan looks for exactly that: four-digit
    credentials, whole, in everything the call sent. An id that can spell one turns a constraint
    that means "none found" into one that fails at random, which is worse than a weaker rule
    honestly stated. Found by the red-team corpus's own B2 scan going red on a random id, 2026-09-10.

    Digits are also the one thing a caller keys, so an identifier that cannot contain one cannot be
    mistaken for keyed input by any future reader of a log or a wire capture either.
    """
    # Prefix carries no frame kind. It used to read `item_`, which stamped the response request as
    # an item and quietly undercut the "which half failed" attribution this exists for
    # (/code-review, 2026-09-10).
    return "evt_" + uuid.uuid4().hex.translate(_DIGIT_FREE)


def _causing_event_id(event):
    """`error.event_id` off an error event, or None -- defensively, and never raising.

    Optional in the specification, and the error object is nested, so every step here is a step
    that can legitimately find nothing. An error event that ends the relay task would end the call,
    which is the one thing an error event must not do.
    """
    return getattr(getattr(event, "error", None), "event_id", None)


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

    # The ids this relay stamped on its own frames, so an `error` naming one can be told from an
    # error about anything else. Bounded rather than a growing set: a call whose credential check
    # keeps coming back unavailable can key indefinitely without ever settling, and a correlation
    # buffer must not grow for as long as such a call runs.
    #
    # **This is a recency window, not a complete record, and it cannot be one.** An earlier comment
    # here claimed the bound "holds every frame a call that ends normally can still be waiting on".
    # That is false: an unavailable credential check produces a spoken sentence and costs no
    # attempt (CONTEXT.md, "Attempt"), so a call can inject without limit and still end normally.
    # No fixed bound covers that, and the claim was the same species of defect -- a comment
    # outrunning its code -- that the review this line came from was fixing (/code-review,
    # 2026-09-10).
    #
    # What the size is actually for: hold enough frames that a rejection arriving while the caller
    # keys on can still be attributed. `MAX_ATTEMPTS` injections at two frames each covers every
    # attempt a call is allowed, with one injection's headroom for a terminal or unavailable
    # outcome on top. Older ids age out on purpose -- an error names the frame that caused it, and
    # that frame is recent. A missed correlation degrades to the unattributed log line, which is
    # where this started.
    injected_frame_ids = collections.deque(maxlen=2 * (auth.MAX_ATTEMPTS + 1))

    await realtime.send(_session_update(agent))

    async def transport_to_model():
        nonlocal auth_state
        while True:
            kind, payload = acs.classify_inbound(await transport.receive_text())
            if kind == acs.DTMF:
                # Arrival, then outcome. **Never the digit** (B2): the tone value goes straight from
                # the classifier into the authenticator and is not held anywhere in between, and
                # neither line below takes it as an argument. Phase 0's R-03 question -- does DTMF
                # arrive during active bidirectional streaming -- is already answered, so this does
                # not need the elapsed-time-since-stream-start the Phase 0 app's log carried.
                #
                # **What the record does reveal, stated rather than denied.** One arrival line per
                # frame means the number of tones a caller keyed is inferable by counting lines, and
                # this comment used to claim otherwise (/code-review, 2026-09-10). That is accepted,
                # not overlooked: B2 protects the credential, and a count of keypresses is not one
                # -- it is exactly what an operator needs to tell a caller who mis-keyed from a
                # caller who never keyed at all. The digits themselves appear in neither line, which
                # is the property B2 actually names.
                #
                # **The term is CONTEXT.md's.** "PIN check", not "PIN entry" -- the glossary lists
                # the latter under Avoid, and a log line is code vocabulary like any other.
                log.info("DTMF frame arrived")
                # The one blocking call on this path: a live credential check against the system of
                # record, awaited inside the inbound loop, so audio frames are not forwarded to the
                # model until it answers. Bounded by the client's own timeout and circuit breaker
                # rather than by anything here -- see `auth/authenticator.py`, which inherits both
                # instead of reimplementing them. Left inline deliberately (/code-review,
                # 2026-09-10): the stall happens on the fourth tone, when the caller has just
                # finished keying and is waiting for a verdict rather than speaking, and putting a
                # second concurrent task on the PIN path to reclaim it would buy a moment of audio
                # nobody is using at the cost of the one ordering guarantee B1 rests on.
                outcome = await authenticator.key(payload)
                log.info("PIN check outcome: %s", outcome)
                if authenticator.is_authenticated:
                    # The one write. Idempotent by construction -- the machine's transition is
                    # one-way, so a later key press cannot bring this back round a second time.
                    auth_state = gate.AUTHENTICATED
                sentence = auth.sentence_for(outcome)
                if sentence is not None:
                    # Told, not left in silence -- the same reason a refusal is spoken rather than
                    # met with nothing. The three silent outcomes are the caller still keying, and
                    # speaking over them is the one thing a PIN prompt cannot afford to do.
                    # **Both frames are stamped, because the mechanism is both frames.** The item
                    # carries the sentence and the response request is what makes it spoken; a
                    # rejection of the second is as much a failure of this injection as a rejection
                    # of the first, and correlating only the item would report the second as an
                    # unrelated error (/code-review, 2026-09-10).
                    item_id = _new_event_id()
                    response_id = _new_event_id()
                    injected_frame_ids.extend((item_id, response_id))
                    await realtime.send(_spoken_note(sentence, item_id))
                    await realtime.send({"type": "response.create", "event_id": response_id})
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
                #
                # **One field is safe and is read**: `error.event_id`, the id of the client frame
                # that caused the error. It is an opaque value this relay generated itself, so it
                # carries nothing of the caller, and it is the only documented way to tell "the
                # item I injected was refused" from "something else went wrong". Phase 5's real
                # call is a probe of that item's shape, and a probe that cannot tell those two
                # apart would send whoever reads it chasing the wrong thing.
                if _causing_event_id(event) in injected_frame_ids:
                    log.error("AOAI rejected a frame of the injected PIN-outcome")
                else:
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

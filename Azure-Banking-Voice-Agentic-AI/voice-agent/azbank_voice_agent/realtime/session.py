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
import time
import uuid

from fastapi import WebSocketDisconnect
from opentelemetry import trace

from .. import auth
from ..agents import specs
from ..call_records import CallRecordStoreUnavailable, EscalationRequested
from ..call_records.store import day_key
from ..cost import caps
from ..dispatch import gate
from ..dispatch.tools import CallScope, dispatch_tool_call
from ..observability import telemetry
from ..transport import acs

log = logging.getLogger("bridge")

# Set explicitly, not left to defaults: this is a paid call, not the earlier text-modality probe
# that confirmed these defaults. Shared by every agent's session.update -- only instructions and
# tools change on a handoff (issue #20), never the audio wire shape.
_AUDIO_CONFIG = {
    "input": {
        "format": {"type": "audio/pcm", "rate": 24000},
        # `silence_duration_ms` raised 200 -> 600, 2026-09-12 (Marco, live on Phase 5's second real
        # call). Open item 9's interrupt-the-caller defect reproduced a third time here, described
        # as talking over the caller "out of control" rather than the earlier one-off -- a stronger
        # signal than the two prior calls gave. 200ms reads an ordinary mid-sentence pause as the
        # caller finishing; 600ms is long enough to survive a breath without making the agent feel
        # sluggish. This is the change open item 9 already named as its fix: turn-detection tuning,
        # not new code, deliberately isolated from everything else so a regression stays
        # attributable to this line and not to Phase 5's intents or greeting.
        "turn_detection": {
            "type": "server_vad",
            "threshold": 0.5,
            "prefix_padding_ms": 300,
            "silence_duration_ms": 600,
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


def _new_idempotency_key():
    """The key one call's card block is made under: unique, opaque, and digit-free.

    **Generated here, not by the model** (issue #47). The tool declares no key parameter at all,
    because a model that could choose its own key could defeat the mechanism by choosing a fresh one
    for every attempt -- which is exactly the repeat the key exists to collapse. Scoped to the call
    for the same reason it is not scoped to the process: two callers must not share a key, and one
    caller's second request must.

    Digit-free through the same translation `_new_event_id` uses, and for the same B2 reason -- see
    that function. The rule lives in one place so a second identifier cannot quietly be exempt from
    it. The prefix is `idem_` so a key and a frame id are not mistaken for each other in a log.
    """
    return "idem_" + uuid.uuid4().hex.translate(_DIGIT_FREE)


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


#: What the caller hears when the day's budget is gone, or cannot be read (issue #49). Composed here
#: like every other sentence the caller hears, and deliberately **the same sentence for both**: a
#: caller who could tell "we are closed" from "we could not check" would have been handed a probing
#: oracle for exactly the condition that costs money.
#:
#: Short on purpose. The closed path is bounded to one turn and a few seconds, and a long apology
#: would be a brake spending money to say it is not spending money.
CLOSED = (
    "Sorry -- the service is closed right now. Please call back later."
)


#: How long the relay waits for the day's ledger before treating silence as a closed day.
#:
#: **A deadline the store cannot be trusted to keep for us.** `core_banking/client.py` passes its
#: own `TIMEOUT_SECONDS` on every request; this seam had nothing equivalent on either side until
#: 2026-09-11, so the guard below is where the bound now lives -- at the seam rather than inside
#: one implementation of it, which is what makes it hold for the fake, the real client, and
#: anything either is later swapped for.
#:
#: Three seconds: long enough that an ordinary Table Storage round trip is nowhere near it, short
#: enough that a caller who is going to hear "we're closed" hears it while still on the line.
LEDGER_DEADLINE_SECONDS = 3.0


async def budget_or_closed(call_records, now=None):
    """Serve this call, or raise `DailyBudgetSpent` -- B4's daily cap, and `T-B4-FAILCLOSED`.

    **Unreadable is the same as exhausted.** A store that raises, times out, or returns something
    this client cannot read produces the same exception an exhausted day does, and therefore the
    same closed path. There is no branch in which an unknown budget serves a call: an unknown budget
    is not permission.

    **Returns nothing. It is a guard, not a query** -- returning normally is the whole answer. It
    used to hand back the day's remaining minutes, which its only caller discarded (/code-review,
    2026-09-11); a number nobody reads is a second, unmaintained account of the budget sitting
    beside the ledger that actually holds it.

    **Where this is called from, and why it is not the webhook.** `docs/phase5/exit-criteria.md`
    criterion 11 said the budget is read "before `answer_call`", in the incoming-call webhook, so a
    call that will not be served costs the webhook and nothing more. It is read here instead, on the
    media socket, and that is a deliberate change recorded rather than a criterion quietly missed:

      * The closed path has to **answer and speak** -- a caller must hear "we're closed" rather than
        a dead line, which is the user story the criterion itself rests on. So the call is answered
        either way, and what the earlier placement actually saved was the realtime connection.
      * A decision made in the webhook has to reach the media socket somehow, and every way of
        carrying it is either process-wide mutable state or a marker in the WebSocket URL. **The
        second is client-controllable**: the media endpoint is public and unauthenticated until
        Phase 7, so a marker there would let whoever opens the socket choose to be served. That is
        fail-open, on the one constraint whose whole point is failing closed.
      * Read here, the check is on the only path a call actually takes and cannot be bypassed.

    The cost of the change is the realtime connection a closed call still opens, which is what the
    closed path needs anyway to say anything at all.
    """
    day = day_key(now)
    try:
        used = await asyncio.wait_for(
            call_records.minutes_used(day), timeout=LEDGER_DEADLINE_SECONDS
        )
    except TimeoutError as e:
        # **Criterion 11's "times out", finally implemented rather than asserted.** Until
        # 2026-09-11 nothing here imposed a deadline and the table client was built without one,
        # so a Storage endpoint that accepted the connection and then said nothing stalled the
        # media socket with a caller already on it -- no closed sentence, no hangup, just silence
        # for as long as the socket stayed open. The only evidence the branch worked was a fake
        # that pre-raised the exception the code was supposed to produce (/code-review,
        # 2026-09-11).
        #
        # Same standing as an unreadable ledger, and deliberately the same exception: a store that
        # did not answer in time did not answer, and B4's rule is that an unknown budget is not
        # permission.
        log.warning("B4: the day's ledger did not answer in time, taking the closed path")
        raise caps.DailyBudgetSpent(
            "the day's ledger did not answer in time", cause=caps.CLOSED_PATH_LEDGER_UNREADABLE,
        ) from e
    except CallRecordStoreUnavailable as e:
        log.warning("B4: the day's ledger could not be read, taking the closed path: %r", e)
        raise caps.DailyBudgetSpent(
            "the day's ledger could not be read", cause=caps.CLOSED_PATH_LEDGER_UNREADABLE,
        ) from e
    if used >= caps.MAX_DAILY_MINUTES:
        log.warning(
            "B4: daily cap reached (%.1f of %.1f minutes for %s), taking the closed path",
            used, caps.MAX_DAILY_MINUTES, day,
        )
        raise caps.DailyBudgetSpent(
            f"the day's {caps.MAX_DAILY_MINUTES} minutes are spent",
            cause=caps.CLOSED_PATH_BUDGET_SPENT,
        )


async def run_closed_call(
    transport, realtime, call_records, correlation_id=None, now=None, closed_path_cause=None,
    capture=None,
):
    """Answer, say the service is closed, hang up. **Hard-bounded, by the relay.**

    One turn and a short wall clock, neither of them the model choosing to be brief (issue #49). A
    closed path that could run for a full call would be a brake that spends money to refuse spending
    money, which is a brake nobody should trust.

    It reuses the injection mechanism Phase 4 built for PIN outcomes -- an item followed by a
    response request -- rather than inventing a second way of making the agent say something it did
    not decide. That is one mechanism to understand, one to review, and one that can go wrong.

    **Its own minutes count too.** Recorded on the way out like any other call, because a brake
    whose usage was invisible in the one place it matters would not be a brake anybody could audit.

    `closed_path_cause` is D13's two-way classification (`caps.CLOSED_PATH_BUDGET_SPENT` /
    `caps.CLOSED_PATH_LEDGER_UNREADABLE`) -- `app.py`'s `media_stream` reads it off the
    `caps.DailyBudgetSpent` it caught and hands it in, because that is where the exception (and
    therefore the classification) actually exists; `budget_or_closed` itself has already returned
    control by the time this runs. Set on the "call" span opened by whichever caller opened it
    (production: `app.py`'s `media_stream`; tests: whatever wraps this call directly), never spoken
    to the caller -- the glossary's probing-oracle reasoning for the sentence itself is untouched.
    """
    started = time.monotonic()
    span = trace.get_current_span()
    span.set_attribute("closed_path_taken", True)
    if closed_path_cause is not None:
        span.set_attribute("closed_path_cause", closed_path_cause)

    async def speak_once():
        """Relay the closed sentence's audio, and stop after `MAX_CLOSED_CALL_TURNS` responses.

        **Counted against the constant rather than returning on the first `response.done`.** The
        bound was previously structural: the relay returned at the first completed response, which
        gave the right answer while `cost/caps.py`'s `MAX_CLOSED_CALL_TURNS` was referenced
        nowhere -- so editing that value changed nothing, and the caps module's claim that the
        relay enforces it was false (/code-review, 2026-09-11). Reading it here is what makes the
        number the bound instead of a description of one.
        """
        # A cap of zero means "no turns at all", and counting `response.done` events could never
        # reach it -- the wall clock would be the only thing ending the path, which is the
        # brake-becomes-the-cost shape this constant exists to prevent. Written as a direct test of
        # the constant: the first version of this guard compared a freshly-assigned `turns = 0`
        # against the cap, which is this line with extra steps (/code-review, 2026-09-11, twice).
        if caps.MAX_CLOSED_CALL_TURNS <= 0:
            return
        turns = 0
        async for event in realtime:
            if event.type == "response.output_audio.delta":
                await transport.send_text(acs.outbound_audio_frame(event.delta))
            elif event.type == "response.done":
                turns += 1
                if turns >= caps.MAX_CLOSED_CALL_TURNS:
                    return
            elif event.type == "error":
                log.error("AOAI error event on the closed path")

    try:
        # **The three frames are inside the `try` too** (/code-review, 2026-09-11). They used to
        # go out above it, between `started` and the block whose `finally` charges the day -- so a
        # closed call that failed on its first frame recorded nothing, against a docstring
        # promising the opposite two paragraphs up.
        #
        # **What the `except` below now also swallows, stated accurately.** An earlier version of
        # this comment said "exactly one case", the caller hanging up during these frames. That
        # undercounted: `TimeoutError` is named in the tuple, so a *send* that times out is caught
        # here too and logged as a path that ended without a complete response. Both are the closed
        # path failing to deliver one sentence, which is the line's meaning, so the branch is right.
        #
        # Two corrections in two reviews on one comment. The first said "exactly one case" and was
        # wrong about the count; the replacement blamed `TimeoutError` subclassing `OSError`, which
        # is true of the type and irrelevant here, since `OSError` appears nowhere in the tuple
        # (/code-review, 2026-09-11, twice).
        await realtime.send(_session_update(gate.TRIAGE_AGENT))
        item_id = _new_event_id()
        await realtime.send(_spoken_note(CLOSED, item_id))
        await realtime.send({"type": "response.create", "event_id": _new_event_id()})
        # Two bounds, and the wall clock is the one that holds if the model never finishes: a turn
        # cap alone would wait forever for a `response.done` that is not coming.
        await asyncio.wait_for(speak_once(), timeout=caps.MAX_CLOSED_CALL_SECONDS)
    except (TimeoutError, WebSocketDisconnect):
        log.warning("closed path ended without a complete response")
    finally:
        await _record_minutes(call_records, started, now)
        span.set_attribute("end_reason", "closed")
        span.set_attribute("auth_state", gate.ANONYMOUS)
        span.set_attribute("duration_ms", telemetry.round_duration_ms(time.monotonic() - started))
        if capture is not None:
            # turn_count 0: the closed path's one fixed sentence is not a counted turn, and it holds
            # no words worth keeping -- the pipeline writes this call's outcome row and nothing more.
            capture.finish(
                correlation_id, "closed", gate.ANONYMOUS, 0,
                telemetry.round_duration_ms(time.monotonic() - started),
            )
    log.info("closed call ended, correlationId=%s", correlation_id)


async def _record_minutes(call_records, started, now=None):
    """Charge the day for what this call actually used. Never raises.

    On **every path out**, which is why it is called from a `finally` (issue #50). A call that
    crashed still counts against the day: minutes that went unrecorded are minutes the cap cannot
    see, and a cap that undercounts fails open.

    A store that cannot be written is logged loudly and swallowed. The call is already over, so
    there is nothing left to refuse -- and raising here would turn a bookkeeping failure into a
    relay failure on a call that had otherwise finished normally.

    **B4's metric is recorded here too, regardless of whether the write below succeeds** (issue
    #61, D14). The minutes were genuinely used either way -- the metric is an observable fact about
    the call, not a mirror of the ledger's own write, which is what stays fail-closed on its own
    terms above and below this function.
    """
    minutes = (time.monotonic() - started) / 60
    telemetry.record_daily_minutes(minutes)
    try:
        # **Bounded, for a reason the read's bound does not cover.** This runs in a `finally`, so a
        # store that accepts the write and never acknowledges it would hang the relay *after* the
        # call is over -- the caller is gone, nothing is left to refuse, and the task would sit
        # there holding the connection. A timeout here is recorded exactly like any other failure
        # to write: loudly, and swallowed (/code-review, 2026-09-11).
        await asyncio.wait_for(
            call_records.record_minutes(day_key(now), minutes),
            timeout=LEDGER_DEADLINE_SECONDS,
        )
    except (CallRecordStoreUnavailable, TimeoutError) as e:
        # **Whole seconds, rounded, never the raw float** (B2). The run-wide scan checks a record's
        # raw formatting arguments as well as its rendered message, and an unrounded duration is
        # seventeen significant digits of essentially random decimals -- which is exactly the
        # alphabet a four-digit credential gets spelled out of by chance. It happened: a duration of
        # 1.7117999959737062e-06 minutes contains "9999", and the scan went red on a call that had
        # leaked nothing.
        #
        # Same reasoning as the digit-free frame ids: a value that can spell a credential turns a
        # constraint meaning "none found" into one that fails at random. Whole seconds are bounded
        # by MAX_CALL_SECONDS and MAX_CLOSED_CALL_SECONDS, so at most three digits, which cannot
        # spell a four-digit run at all.
        log.error(
            "B4: %ds were NOT recorded against the day's ledger -- the cap is now undercounting "
            "by that much: %s", round(minutes * 60), type(e).__name__,
        )


async def run_call(
    transport, realtime, core_banking, call_records, correlation_id=None, now=None, capture=None,
):
    """Relay one call: media transport <-> realtime connection, with core banking behind the gate.

    `transport` satisfies transport.protocol.MediaTransport; `realtime` satisfies
    realtime.client.RealtimeConnection; `core_banking` satisfies core_banking.CoreBankingClient;
    `call_records` satisfies call_records.CallRecordStore. None of the four is constructed here --
    that is what lets a whole call run against fakes with no patching (issue #18, extended to the
    third collaborator by issue #28 and to the fourth by issue #48).

    `correlation_id` is ACS's own id for this call, read off the media WebSocket's headers by
    `app.py` and **handed in rather than fetched**: the relay takes its collaborators, and a relay
    that reached back through the transport for a header would be a relay that knew what kind of
    transport it had. It defaults to None because the probe and every fake-driven test genuinely
    have no such id, and an escalation record carrying None is a record that says so rather than a
    record that lies.

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
    started = time.monotonic()
    agent = gate.TRIAGE_AGENT
    auth_state = gate.ANONYMOUS

    # One per call, holding this caller's keypad and their attempts. Constructed here because this
    # is where the call's auth state already lives, and given the same core-banking client the
    # dispatcher gets -- which is what makes an unreachable service fail authentication closed
    # without a second fail-closed path (issue #35).
    authenticator = auth.Authenticator(core_banking)

    # One key for this call's card block, generated before anything can ask for one (issue #47).
    # Built once per call rather than per tool call, which is the whole mechanism: a model that
    # calls block_card twice sends the same key twice and the system of record answers the second
    # from its record of the first. A key made per tool call would be two different keys and two
    # attempts at blocking.
    idempotency_key = _new_idempotency_key()

    # Everything call-scoped a tool may need, in one object handed to every tool call. Built once,
    # here, where the call's state already lives -- the dispatcher never reaches for any of it.
    scope = CallScope(
        core_banking=core_banking,
        call_records=call_records,
        idempotency_key=idempotency_key,
        correlation_id=correlation_id,
    )

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
        # Issue #61: the same pairing, now also recorded as B5's histogram rather than only
        # readable from the order of two log lines. `speech_stopped_at` is cleared once the paired
        # audio delta arrives -- and left alone across a tool-call-only response.done exactly as
        # `audio_started` is, for the reason the comment above already gives.
        speech_stopped_at = None
        # Issue #61 (D5): one "turn" span per response cycle. `turn_started` marks where the
        # current one began -- the call's own start for the first turn, the previous
        # response.done for every one after.
        turn_started = time.monotonic()
        # Set when escalate_to_human succeeds; consumed at a later response.done, not necessarily
        # the next one. Fixes a bug live 2026-09-14: raising EscalationRequested immediately after
        # response.create stopped this coroutine from ever reaching the response.output_audio.delta
        # events for the model's closing remark, so escalated calls ended in silence -- the exact
        # failure issue #48's own comment (below) says this ordering was meant to prevent.
        #
        # **Why "a later" and not "the next" response.done, and why `response_had_a_tool_call`
        # exists**: the response that calls escalate_to_human gets its own response.done -- no
        # audio, same as any tool-call-only response (`audio_started`'s comment above; confirmed
        # live 2026-09-14, every tool-call turn's `agent_spoke` attribute is False) -- *before* the
        # new response requested by `response.create` (the one that might actually speak) is even
        # created. A flag consumed on that first response.done, as an earlier version of this fix
        # did, fires one response too early -- silence, again, just one event later. So: skip any
        # response.done whose response itself contained a tool call (this response cycle's own),
        # and only raise on the first one that didn't -- which generalises correctly however many
        # further tool calls the model makes before it actually speaks.
        pending_escalation = False
        response_had_a_tool_call = False
        async for event in realtime:
            if event.type == "response.output_audio.delta":
                if not audio_started:
                    audio_started = True
                    log.info("agent audio started")
                    if speech_stopped_at is not None:
                        telemetry.record_turn_latency(time.monotonic() - speech_stopped_at)
                        speech_stopped_at = None
                await transport.send_text(acs.outbound_audio_frame(event.delta))
            elif event.type == "input_audio_buffer.speech_stopped":
                # Server VAD's turn-ended signal -- confirmed live 2026-09-08, see
                # realtime/fake.py's speech_stopped().
                log.info("caller turn ended")
                speech_stopped_at = time.monotonic()
            elif event.type == "response.function_call_arguments.done":
                # Every tool call, handoff included, marks its own response as tool-call-only --
                # see `response_had_a_tool_call`'s comment above. Set unconditionally, before the
                # handoff/dispatch split below, so a pending escalation is never consumed by this
                # response's own response.done regardless of which branch actually runs.
                response_had_a_tool_call = True
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
                    event.name, event.arguments, agent, auth_state, scope=scope,
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
                # **After the output is sent and a response is asked for, never before** (issue
                # #48). The caller hears an apology because the model is given something to say and
                # asked to say it -- which requires actually waiting for that response's audio
                # (see `pending_escalation` above), not just requesting it and ending the call.
                #
                # Read off the output rather than off the tool name alone: an escalation the gate
                # refused, or one whose reason code the model invented, comes back as an error and
                # must not end the call -- the caller is told to say it again, which is what every
                # other malformed tool call already does.
                if event.name == "escalate_to_human" and "error" not in json.loads(output):
                    log.info("escalation requested, call ends after this response is spoken")
                    pending_escalation = True
            elif event.type == "response.output_audio_transcript.delta":
                # The only transcript available without provisioning a separate transcription
                # deployment (see the input_audio_transcription comment above) -- what the agent
                # said, not what the caller said. Arrival only, never the words (B2): the moment
                # the agent can ever repeat something sensitive back, this is the log line that
                # would carry it, so no content lands here now either -- no exception carved out
                # for Phase 2 just because there's nothing sensitive to say yet.
                log.info("agent transcript delta received (%d chars)", len(event.delta))
                # Phase 8 (D14): held in memory for the post-call pipeline, which redacts before
                # anything is written (ADR-007). Nothing about this line reaches a log.
                if capture is not None:
                    capture.add_delta(event.delta)
            elif event.type == "response.done":
                # One full model response cycle = one turn (B4).
                turn_count += 1
                if capture is not None:
                    capture.end_turn()
                # Issue #61 (D5): the "turn" span, created and closed here rather than opened at
                # the top of the loop and held open -- a turn is only known to be over at this
                # event, so it is recorded retroactively (`start_span` + `end()`, not
                # `start_as_current_span`) with its real elapsed time as the `duration_ms`
                # attribute. `turn_started` rolls forward to this moment for the next one.
                turn_span = telemetry.tracer().start_span(telemetry.TURN)
                turn_span.set_attribute("turn_index", turn_count)
                turn_span.set_attribute(
                    "duration_ms", telemetry.round_duration_ms(time.monotonic() - turn_started)
                )
                turn_span.set_attribute("agent_spoke", audio_started)
                turn_span.end()
                turn_started = time.monotonic()
                audio_started = False  # B5: next audio delta is a new response cycle's first.
                # Checked before the turn cap below (/code-review, 2026-09-14): the closing
                # remark's own response.done can be the same one that trips MAX_CALL_TURNS -- the
                # audio was already relayed above either way, so the only question left is which
                # exception type reports it. Checking the cap first would raise CallLimitExceeded
                # and log this as a cost event, even though the caller was actually escalated and
                # #48 asks that a routing event and a cost event stay distinguishable in every log
                # that reads them. Escalation wins the race: its own condition already means "the
                # apology has been spoken, end the call," and that is true regardless of what the
                # turn count also happens to be on this same event.
                if pending_escalation and not response_had_a_tool_call:
                    # This response.done's own response called no further tool -- it is the
                    # escalation's actual closing remark (or the model chose to say nothing, which
                    # is equally a real, spoken-or-not response rather than the tool-call response
                    # itself), and every response.output_audio.delta it had was already relayed
                    # above, in event order, before this response.done could fire. Ending the call
                    # here is the actual fix (see `pending_escalation`'s own comment) -- a version
                    # of this fix that skipped `response_had_a_tool_call` fired here one response
                    # too early, on the tool-call response itself, before this one even started.
                    log.info("escalation response delivered, ending call")
                    raise EscalationRequested("the caller was escalated to a person")
                if turn_count >= caps.MAX_CALL_TURNS:
                    log.warning("call hit MAX_CALL_TURNS=%d, ending call (B4)", caps.MAX_CALL_TURNS)
                    raise caps.CallLimitExceeded(f"turn cap ({caps.MAX_CALL_TURNS}) reached")
                response_had_a_tool_call = False
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
        # /code-review, 2026-09-14: the gap on the other side of the same fix. If the event stream
        # ends -- the connection drops, or (in tests) the fake simply runs out of scripted events --
        # while `pending_escalation` is still True, the loop above exits normally and this coroutine
        # would otherwise just return. The record was already written before this flag was ever set
        # (`dispatch_tool_call`, above), so the call *is* an escalation regardless of whether its
        # closing remark's response.done ever arrived -- letting it fall through here would report
        # it as `end_reason="model_ended"`, exactly the misclassification #48 asks this exception
        # type exists to prevent.
        if pending_escalation:
            log.info("escalation pending when the connection ended, ending call")
            raise EscalationRequested("the caller was escalated to a person")

    # Issue #61: the "call" span's `end_reason` default -- overwritten by the classification below
    # once the tasks actually finish. Stays "error" only if something raises before that
    # classification ever runs (e.g. the greeting frame itself), which is an accurate label for
    # that case too.
    end_reason = "error"
    try:
        # **Inside the `try`, so the `finally` below covers these two frames.** They used to sit
        # above it: `started` was taken, three frames went out, and only then did the block whose
        # `finally` records minutes and ends the auth state open. A realtime send that raised here
        # skipped both, so a call that reached AOAI and burned wall clock left nothing in the day's
        # ledger -- while `_record_minutes`'s own docstring said "on every path out"
        # (/code-review, 2026-09-11). Moved below the nested definitions rather than dragging them
        # into the block: defining a coroutine function has no side effect, so the order frames
        # actually go out in is unchanged.
        await realtime.send(_session_update(agent))
        # **The greeting, asked for rather than waited for** (issue #51). Without this the agent says
        # nothing until the caller speaks first and server-side turn detection fires -- every real call
        # so far has shown 2.5 to 11 seconds of dead air, varying only with how quickly the caller
        # talked.
        #
        # It was parked at Phase 3 kickoff and again at Phase 4's, as a greeting-path defect rather than
        # an auth-path one. It stopped being parkable in the phase whose exit depends on a caller keying
        # a PIN they were never asked for: the greeting is the thing that asks for it, so a caller who
        # says nothing was waiting on a prompt that had not been triggered and never would be.
        #
        # One frame, here, and nothing else in this phase touches it -- so a regression on the first
        # real call is attributable to this or to the intents and never to both. For the same reason
        # `server_vad` is untouched: changing when the agent first speaks *and* how it detects turns in
        # one phase would make the interrupt-the-caller defect unattributable too.
        await realtime.send({"type": "response.create"})

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
            end_reason = "timeout"
        for task in done:
            exc = task.exception()
            # Expected ways a call ends, not relay failures: the caller hung up, a B4 cap tripped,
            # or the caller ran out of PIN attempts. AttemptsExhausted travels this same branch
            # with its own type rather than reusing CallLimitExceeded, so a security event and a
            # cost event stay distinguishable in every log that ever reads them.
            # Escalation joins the list with its own type, for the reason AttemptsExhausted has
            # one: a routing event, a security event and a cost event stay distinguishable in every
            # log that ever reads them.
            expected = (
                WebSocketDisconnect,
                caps.CallLimitExceeded,
                auth.AttemptsExhausted,
                EscalationRequested,
            )
            # Issue #61: the "call" span's `end_reason`, classified alongside the control flow
            # above rather than re-derived from it later -- a for-loop over `done` can visit more
            # than one task, so the last one it processes before any `raise` is what this reports,
            # exactly mirroring which exception (if any) actually decides the call's fate here.
            if exc is None:
                end_reason = "model_ended"
            elif isinstance(exc, WebSocketDisconnect):
                end_reason = "caller_hangup"
            elif isinstance(exc, caps.CallLimitExceeded):
                end_reason = "cost_cap"
            elif isinstance(exc, auth.AttemptsExhausted):
                end_reason = "attempts_exhausted"
            elif isinstance(exc, EscalationRequested):
                end_reason = "escalated"
            if exc is not None and not isinstance(exc, expected):
                end_reason = "error"
                raise exc
    finally:
        # The third point the buffer is zeroed at, after submit and clear -- on call end, whatever
        # the outcome. In a finally because "whatever the outcome" includes the paths that raise.
        authenticator.end_call()
        # And the day is charged for this call, on every path out -- a clean hangup, either B4 cap,
        # exhausted attempts, an escalation, or an unhandled failure (issue #50). A call that ended
        # badly still counts against the day, because minutes the cap cannot see are minutes it
        # fails open on.
        await _record_minutes(call_records, started, now)
        # Issue #61 (D5): the "call" span's own attributes, set on whatever span is currently open
        # (production: app.py's media_stream; tests: whatever wraps run_call directly) -- on every
        # path out, including the ones above that raise, which is why this is in the same finally.
        span = trace.get_current_span()
        span.set_attribute("auth_state", auth_state)
        span.set_attribute("end_reason", end_reason)
        span.set_attribute("turn_count", turn_count)
        span.set_attribute("duration_ms", telemetry.round_duration_ms(time.monotonic() - started))
        span.set_attribute("closed_path_taken", False)
        if capture is not None:
            capture.finish(
                correlation_id, end_reason, auth_state, turn_count,
                telemetry.round_duration_ms(time.monotonic() - started),
            )
    log.info("call ended")

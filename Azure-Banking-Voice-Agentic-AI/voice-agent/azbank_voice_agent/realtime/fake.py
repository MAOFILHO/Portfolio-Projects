"""A scriptable stand-in for the Azure OpenAI realtime deployment.

Satisfies `realtime.client.RealtimeConnection` structurally, so `run_call` cannot tell the
difference. **Nothing in this module makes a network call, ever** -- it replays a list of events
and records what was sent to it.

Event names and shapes are the ones confirmed live against the real deployment in Phase 1
(docs/phase1/research-aoai-realtime-wire-format.md, plus the probe that corrected the outbound
audio event name to response.output_audio.delta). A fake that replays the wrong event names would
pass tests and fail on a real call, so these builders exist rather than tests hand-rolling
dictionaries.

Shape borrowed from the sibling project's fake model client
(AWS-Insurance-FNOL-Voice-Agentic-AI, `agents/testing/fake_llm.py`).
"""
import asyncio
from types import SimpleNamespace


def audio_delta(b64_payload="BBBB"):
    """The model speaking one chunk of audio."""
    return SimpleNamespace(type="response.output_audio.delta", delta=b64_payload)


def transcript_delta(text):
    """What the model said, in text. The only transcript available without provisioning a
    separate transcription deployment -- agent speech, never caller speech."""
    return SimpleNamespace(type="response.output_audio_transcript.delta", delta=text)


def function_call(name, arguments_json, call_id="call-1"):
    """The model asking for a tool. Terminal event of the streamed-arguments sequence."""
    return SimpleNamespace(
        type="response.function_call_arguments.done",
        name=name,
        arguments=arguments_json,
        call_id=call_id,
    )


def speech_stopped():
    """Server VAD's turn-ended signal, server -> client. **Confirmed live 2026-09-08** (Call 2,
    PROJECT_STATE.md): the real deployment emits this exact event type and shape, and it produced
    real B5 turn-latency numbers (297/570/440/280ms) paired against the next audio delta."""
    return SimpleNamespace(type="input_audio_buffer.speech_stopped")


def response_done():
    """One full model response cycle completed -- one turn, for B4's per-call turn cap."""
    return SimpleNamespace(type="response.done")


def error_event(message="something went wrong"):
    """An error event from the model. Must be logged, never fatal to the call."""
    return SimpleNamespace(type="error", message=message)


class FakeRealtimeServer:
    """Replays `events` in order, and records every message sent to it.

    `respond_after_appends` holds the scripted events back until that many audio buffer appends
    have arrived -- the caller speaks, then the model answers. This is what makes a whole-call
    test deterministic rather than a race between the inbound and outbound relay tasks, and it
    mirrors how the real deployment behaves under server-side turn detection.

    `hang=True` blocks forever once the events are drained, instead of ending the iteration, for
    tests where something other than the model should end the call.
    """

    def __init__(self, events=(), respond_after_appends=0, hang=False):
        self.sent = []
        self.consumed = 0
        self._events = list(events)
        self._hang = hang
        self._respond_after = respond_after_appends
        self._appends = 0
        self._released = asyncio.Event()
        if self._respond_after <= 0:
            self._released.set()

    async def send(self, message):
        self.sent.append(message)
        if message.get("type") == "input_audio_buffer.append":
            self._appends += 1
            if self._appends >= self._respond_after:
                self._released.set()

    def __aiter__(self):
        return self

    async def __anext__(self):
        await self._released.wait()
        if self._events:
            self.consumed += 1
            return self._events.pop(0)
        if self._hang:
            await asyncio.Future()  # never resolves; only a cancel() ends this
        raise StopAsyncIteration

    # --- read-side helpers, so tests assert on meaning rather than dict spelunking ---

    @property
    def sent_types(self):
        return [m["type"] for m in self.sent]

    @property
    def appended_audio(self):
        """Base64 payloads the relay forwarded to the model -- what the model 'heard'."""
        return [m["audio"] for m in self.sent if m["type"] == "input_audio_buffer.append"]

    @property
    def tool_outputs(self):
        """(call_id, output) for every function_call_output the relay returned."""
        return [
            (m["item"]["call_id"], m["item"]["output"])
            for m in self.sent
            if m["type"] == "conversation.item.create"
            and m["item"].get("type") == "function_call_output"
        ]

    @property
    def session_config(self):
        """The session.update payload the relay opened with, or None if it never sent one."""
        for m in self.sent:
            if m["type"] == "session.update":
                return m["session"]
        return None

    @property
    def session_configs(self):
        """Every session.update payload sent, in order -- more than one means the call
        reconfigured the session at least once (issue #20's handoff), always on this same
        connection, never a second one."""
        return [m["session"] for m in self.sent if m["type"] == "session.update"]


class FakeRealtimeConnectCM:
    """Async context manager wrapper, matching what the real client's connect() returns."""

    def __init__(self, server):
        self._server = server

    async def __aenter__(self):
        return self._server

    async def __aexit__(self, *exc_info):
        return False

"""Relay tests -- one whole call, driven by hand-rolled doubles for both sides.

Phase 2.1 restructure (issue #17): the dispatch cases moved to test_tools.py; what stays here is
everything that exercises the relay itself. Intent unchanged from Phase 1 -- same cases, same
assertions, retargeted at the modules the code now lives in.

The two doubles below are the seed of issue #18's real FakeTransport and FakeRealtimeServer. They
stay test-local until that ticket promotes them into importable modules.
"""
import asyncio
import json
import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import WebSocketDisconnect

from azbank_voice_agent.cost import caps
from azbank_voice_agent.realtime import session

_ENV = {
    "AOAI_KEY": "fake-key",
    "AOAI_ENDPOINT": "https://fake.example.com",
    "AOAI_DEPLOYMENT": "gpt-realtime-mini",
}


class _FakeAoaiConnection:
    """Stands in for the object yielded by `async with client.realtime.connect(...) as aoai` --
    records every message sent to it, and yields `events` in order (default: none, so `async for`
    ends immediately). `hang=True` makes it block forever once `events` is drained, instead of
    ending the iteration -- for testing the duration cap, where nothing short of that cap should
    end the call."""

    def __init__(self, events=None, hang=False):
        self.sent = []
        self.consumed = 0
        self._events = list(events) if events else []
        self._hang = hang

    async def send(self, message):
        self.sent.append(message)

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self._events:
            self.consumed += 1
            return self._events.pop(0)
        if self._hang:
            await asyncio.Future()  # never resolves; only a cancel() ends this
        raise StopAsyncIteration


class _FakeRealtimeConnectCM:
    def __init__(self, connection):
        self._connection = connection

    async def __aenter__(self):
        return self._connection

    async def __aexit__(self, *exc_info):
        return False


def _fake_async_openai_factory(models_connected, connections, events=None, hang=False):
    """Returns a stand-in for the AsyncOpenAI class. `.realtime.connect(model=...)` records the
    requested model name into models_connected and the connection it hands back into connections,
    so a test can assert on both without touching a real network. `events`/`hang` pass straight
    through to the `_FakeAoaiConnection` -- see its docstring."""

    class _FakeRealtime:
        def connect(self, model):
            models_connected.append(model)
            connection = _FakeAoaiConnection(events, hang=hang)
            connections.append(connection)
            return _FakeRealtimeConnectCM(connection)

    class _FakeAsyncOpenAI:
        def __init__(self, **kwargs):
            self.realtime = _FakeRealtime()

    return _FakeAsyncOpenAI


class _FakeAcsWs:
    """Feeds `frames` (already-JSON-encoded strings) to receive_text() in order, then disconnects
    -- same contract as a real ACS media WebSocket once the caller hangs up. `hang=True` blocks
    forever once `frames` is drained instead of disconnecting -- for testing the duration cap."""

    def __init__(self, frames, hang=False):
        self._frames = list(frames)
        self._hang = hang
        self.sent = []

    async def receive_text(self):
        if self._frames:
            return self._frames.pop(0)
        if self._hang:
            await asyncio.Future()  # never resolves; only a cancel() ends this
        raise WebSocketDisconnect()

    async def send_text(self, text):
        self.sent.append(text)


class RunBridgeUsesConfiguredDeployment(unittest.TestCase):
    """run_bridge must read the realtime deployment name from AOAI_DEPLOYMENT at call time, the
    same way it already reads AOAI_KEY/AOAI_ENDPOINT -- not a hardcoded module constant. B3
    (CLAUDE.md) treats a pin rotation as an expected, scheduled event; a hardcoded deployment name
    would mean rotating the pin requires editing the relay itself."""

    def test_connect_is_called_with_the_env_deployment_name_not_a_hardcoded_one(self):
        models_connected, connections = [], []
        env = dict(_ENV, AOAI_DEPLOYMENT="gpt-realtime-mini-successor")
        with patch.dict(os.environ, env), \
             patch.object(session, "AsyncOpenAI", _fake_async_openai_factory(models_connected, connections)):
            asyncio.run(session.run_bridge(_FakeAcsWs([])))
        self.assertEqual(models_connected, ["gpt-realtime-mini-successor"])


class AcsToAoaiDtmfFrames(unittest.TestCase):
    """DTMF frames must never reach AOAI (out of scope for realtime audio input, unchanged), but
    arrival should still be logged -- minus the raw tone value (B2). Since the Phase 2.1
    restructure the tone value cannot reach this module at all: transport/acs.py's
    classify_inbound never returns it."""

    def test_dtmf_frame_is_logged_and_never_forwarded_to_aoai(self):
        models_connected, connections = [], []
        frames = [json.dumps({"kind": "DtmfData", "dtmfData": {"data": "5"}})]
        with patch.dict(os.environ, _ENV), \
             patch.object(session, "AsyncOpenAI", _fake_async_openai_factory(models_connected, connections)), \
             self.assertLogs(session.log, level="INFO") as cm:
            asyncio.run(session.run_bridge(_FakeAcsWs(frames)))
        self.assertTrue(any("DTMF" in line for line in cm.output))
        self.assertFalse(any('"5"' in line or "tone 5" in line for line in cm.output))
        sent_types = [m["type"] for m in connections[0].sent]
        self.assertEqual(sent_types, ["session.update"])  # never input_audio_buffer.append


class RunBridgeEnforcesB4Caps(unittest.TestCase):
    """B4 (CLAUDE.md): no call exceeds 20 turns / 5 minutes, fails closed. This is a Phase-1-sized
    guard only -- a bare per-call counter and wall-clock timeout, not the full cost-store/daily-cap
    system (docs/PLAN.md Phase 5, `cost/caps.py`'s own docstring, `T-B4-FAILCLOSED`)."""

    def test_turn_cap_ends_the_call_without_draining_every_queued_event(self):
        models_connected, connections = [], []
        events = [SimpleNamespace(type="response.done") for _ in range(5)]
        with patch.dict(os.environ, _ENV), \
             patch.object(session, "AsyncOpenAI",
                           _fake_async_openai_factory(models_connected, connections, events=events)), \
             patch.object(caps, "MAX_CALL_TURNS", 2), \
             self.assertLogs(session.log, level="WARNING") as cm:
            asyncio.run(session.run_bridge(_FakeAcsWs([])))
        # Stopped at the cap (2), not after draining all 5 queued events.
        self.assertEqual(connections[0].consumed, 2)
        self.assertTrue(any("MAX_CALL_TURNS" in line for line in cm.output))

    def test_duration_cap_ends_a_call_that_never_hits_the_turn_cap(self):
        models_connected, connections = [], []
        with patch.dict(os.environ, _ENV), \
             patch.object(session, "AsyncOpenAI",
                           _fake_async_openai_factory(models_connected, connections, hang=True)), \
             patch.object(caps, "MAX_CALL_SECONDS", 0.05), \
             self.assertLogs(session.log, level="WARNING") as cm:
            asyncio.run(session.run_bridge(_FakeAcsWs([], hang=True)))
        self.assertTrue(any("MAX_CALL_SECONDS" in line for line in cm.output))


if __name__ == "__main__":
    unittest.main()

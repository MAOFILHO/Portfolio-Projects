import asyncio
import json
import os
import pathlib
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "voice-agent"))

import accounts  # noqa: E402
import bridge  # noqa: E402
from fastapi import WebSocketDisconnect  # noqa: E402

_ENV = {
    "AOAI_KEY": "fake-key",
    "AOAI_ENDPOINT": "https://fake.example.com",
    "AOAI_DEPLOYMENT": "gpt-realtime-mini",
}


class _FakeAoaiConnection:
    """Stands in for the object yielded by `async with client.realtime.connect(...) as aoai` --
    records every message sent to it, and yields no events (async for ends immediately)."""

    def __init__(self):
        self.sent = []

    async def send(self, message):
        self.sent.append(message)

    def __aiter__(self):
        return self

    async def __anext__(self):
        raise StopAsyncIteration


class _FakeRealtimeConnectCM:
    def __init__(self, connection):
        self._connection = connection

    async def __aenter__(self):
        return self._connection

    async def __aexit__(self, *exc_info):
        return False


def _fake_async_openai_factory(models_connected, connections):
    """Returns a stand-in for the AsyncOpenAI class. `.realtime.connect(model=...)` records the
    requested model name into models_connected and the connection it hands back into connections,
    so a test can assert on both without touching a real network."""

    class _FakeRealtime:
        def connect(self, model):
            models_connected.append(model)
            connection = _FakeAoaiConnection()
            connections.append(connection)
            return _FakeRealtimeConnectCM(connection)

    class _FakeAsyncOpenAI:
        def __init__(self, **kwargs):
            self.realtime = _FakeRealtime()

    return _FakeAsyncOpenAI


class _FakeAcsWs:
    """Feeds `frames` (already-JSON-encoded strings) to receive_text() in order, then disconnects
    -- same contract as a real ACS media WebSocket once the caller hangs up."""

    def __init__(self, frames):
        self._frames = list(frames)
        self.sent = []

    async def receive_text(self):
        if self._frames:
            return self._frames.pop(0)
        raise WebSocketDisconnect()

    async def send_text(self, text):
        self.sent.append(text)


class DispatchToolCall(unittest.TestCase):
    def setUp(self):
        accounts.ACCOUNTS.clear()
        accounts.ACCOUNTS.update({"chequing": 2400.0, "savings": 500.0})

    def test_get_balance_returns_result(self):
        out = json.loads(bridge.dispatch_tool_call("get_balance", '{"account": "chequing"}'))
        self.assertEqual(out, {"result": 2400.0})

    def test_transfer_mutates_and_returns_confirmation(self):
        out = json.loads(bridge.dispatch_tool_call(
            "transfer", '{"from_account": "chequing", "to_account": "savings", "amount": 150.0}'
        ))
        self.assertIn("150", out["result"])
        self.assertEqual(accounts.get_balance("chequing"), 2250.0)

    def test_list_accounts_returns_result(self):
        out = json.loads(bridge.dispatch_tool_call("list_accounts", "{}"))
        self.assertEqual(out, {"result": {"chequing": 2400.0, "savings": 500.0}})

    def test_unknown_account_comes_back_as_error_not_exception(self):
        out = json.loads(bridge.dispatch_tool_call("get_balance", '{"account": "bitcoin"}'))
        self.assertIn("error", out)

    def test_non_positive_amount_comes_back_as_error_not_exception(self):
        out = json.loads(bridge.dispatch_tool_call(
            "transfer", '{"from_account": "chequing", "to_account": "savings", "amount": -500.0}'
        ))
        self.assertIn("error", out)

    def test_unknown_tool_name_comes_back_as_error_not_exception(self):
        out = json.loads(bridge.dispatch_tool_call("delete_account", "{}"))
        self.assertIn("error", out)

    def test_missing_argument_comes_back_as_error_not_exception(self):
        out = json.loads(bridge.dispatch_tool_call("get_balance", "{}"))
        self.assertIn("error", out)


class ToolsMatchDispatch(unittest.TestCase):
    def test_every_declared_tool_is_dispatchable_and_vice_versa(self):
        # TOOLS is what the model sees; _DISPATCH is what actually runs. If they drift, the model
        # calls something that doesn't exist and the call fails mid-conversation.
        declared = {tool["name"] for tool in bridge.TOOLS}
        dispatchable = set(bridge._DISPATCH)
        self.assertEqual(declared, dispatchable)


class RunBridgeUsesConfiguredDeployment(unittest.TestCase):
    """run_bridge must read the realtime deployment name from AOAI_DEPLOYMENT at call time, the
    same way it already reads AOAI_KEY/AOAI_ENDPOINT -- not a hardcoded module constant. B3
    (CLAUDE.md) treats a pin rotation as an expected, scheduled event; a hardcoded deployment name
    would mean rotating the pin requires editing bridge.py itself."""

    def test_connect_is_called_with_the_env_deployment_name_not_a_hardcoded_one(self):
        models_connected, connections = [], []
        env = dict(_ENV, AOAI_DEPLOYMENT="gpt-realtime-mini-successor")
        with patch.dict(os.environ, env), \
             patch.object(bridge, "AsyncOpenAI", _fake_async_openai_factory(models_connected, connections)):
            asyncio.run(bridge.run_bridge(_FakeAcsWs([])))
        self.assertEqual(models_connected, ["gpt-realtime-mini-successor"])


class AcsToAoaiDtmfFrames(unittest.TestCase):
    """DTMF frames must never reach AOAI (out of scope for realtime audio input, unchanged), but
    arrival should still be logged -- the Phase 0 R-03 evidence log's replacement, minus the raw
    tone value (B2) and minus the Phase-0-specific elapsed-time-since-stream-start, since R-03
    itself is already answered (docs/phase1/research-aoai-realtime-wire-format.md)."""

    def test_dtmf_frame_is_logged_and_never_forwarded_to_aoai(self):
        models_connected, connections = [], []
        frames = [json.dumps({"kind": "DtmfData", "dtmfData": {"data": "5"}})]
        with patch.dict(os.environ, _ENV), \
             patch.object(bridge, "AsyncOpenAI", _fake_async_openai_factory(models_connected, connections)), \
             self.assertLogs(bridge.log, level="INFO") as cm:
            asyncio.run(bridge.run_bridge(_FakeAcsWs(frames)))
        self.assertTrue(any("DTMF" in line for line in cm.output))
        sent_types = [m["type"] for m in connections[0].sent]
        self.assertEqual(sent_types, ["session.update"])  # never input_audio_buffer.append

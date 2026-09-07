"""Live-connection wiring.

Carries forward the Phase 1 case that used to live in the relay's own test file: the realtime
deployment name must be read from the environment at call time, never hardcoded. B3 (CLAUDE.md)
treats a pin rotation as an expected, scheduled event; a hardcoded deployment name would mean
rotating the pin requires editing code. The logic moved to realtime/client.py in issue #18, so
the test moved with it -- intent unchanged.
"""
import os
import unittest
from unittest.mock import patch

from azbank_voice_agent.realtime import client

_ENV = {
    "AOAI_KEY": "fake-key",
    "AOAI_ENDPOINT": "https://fake.example.com",
    "AOAI_DEPLOYMENT": "gpt-realtime-mini",
}


def _fake_async_openai_factory(models_connected, kwargs_seen):
    class _FakeRealtime:
        def connect(self, model):
            models_connected.append(model)
            return object()

    class _FakeAsyncOpenAI:
        def __init__(self, **kwargs):
            kwargs_seen.append(kwargs)
            self.realtime = _FakeRealtime()

    return _FakeAsyncOpenAI


class ConnectRealtimeReadsConfigAtCallTime(unittest.TestCase):
    def test_connect_uses_the_env_deployment_name_not_a_hardcoded_one(self):
        models_connected, kwargs_seen = [], []
        env = dict(_ENV, AOAI_DEPLOYMENT="gpt-realtime-mini-successor")
        with patch.dict(os.environ, env), \
             patch.object(client, "AsyncOpenAI", _fake_async_openai_factory(models_connected, kwargs_seen)):
            client.connect_realtime()
        self.assertEqual(models_connected, ["gpt-realtime-mini-successor"])

    def test_the_endpoint_becomes_the_ga_websocket_path(self):
        # GA path, confirmed live in Phase 1: wss, /openai/v1, deployment in model= (asserted
        # above), and no api-version parameter -- that form is the deprecated beta path.
        models_connected, kwargs_seen = [], []
        with patch.dict(os.environ, _ENV), \
             patch.object(client, "AsyncOpenAI", _fake_async_openai_factory(models_connected, kwargs_seen)):
            client.connect_realtime()
        base_url = kwargs_seen[0]["websocket_base_url"]
        self.assertEqual(base_url, "wss://fake.example.com/openai/v1")
        self.assertNotIn("api-version", base_url)

    def test_a_missing_deployment_pin_fails_closed(self):
        # No default: a missing pin must raise, never silently fall back to another deployment
        # (B3, CLAUDE.md).
        env = {k: v for k, v in _ENV.items() if k != "AOAI_DEPLOYMENT"}
        with patch.dict(os.environ, env, clear=True), self.assertRaises(KeyError):
            client.connect_realtime()


if __name__ == "__main__":
    unittest.main()

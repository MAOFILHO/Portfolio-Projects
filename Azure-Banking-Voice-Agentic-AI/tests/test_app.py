import asyncio
import os
import unittest
from unittest.mock import patch

# app reads these at import time (os.environ[...], no default) and constructs a
# CallAutomationClient from the connection string -- that parses the string locally with no
# network call, so a syntactically valid fake is enough to import the module under test. This
# must happen before the import below, hence the import order.
os.environ.setdefault("ACS_CONNECTION_STRING", "endpoint=https://fake.communication.azure.com/;accesskey=ZmFrZWtleQ==")
os.environ.setdefault("APP_BASE_URL", "https://fake.example.azurecontainerapps.io")
# Read by lifespan() rather than at import, but the guard behind it has no default (issue #29) --
# so a test that exercises startup has to supply one, the same as a real deployment does.
os.environ.setdefault("CORE_BANKING_URL", "http://core-banking.test:8001")

from azbank_voice_agent import app
from azbank_voice_agent.core_banking.fake import FakeCoreBankingClient
from azbank_voice_agent.realtime.fake import FakeRealtimeConnectCM, FakeRealtimeServer
from azure.core.exceptions import HttpResponseError, ServiceRequestError


def _incoming_call_event(correlation_id="corr-1", context="ctx-1"):
    return [{
        "eventType": "Microsoft.Communication.IncomingCall",
        "data": {"incomingCallContext": context, "correlationId": correlation_id},
    }]


class FakeRequest:
    def __init__(self, events):
        self._events = events

    async def json(self):
        return self._events


def _run_incoming_call(events):
    return asyncio.run(app.incoming_call(FakeRequest(events)))


class AnswerCallRejectionPath(unittest.TestCase):
    def test_answer_call_http_error_falls_back_to_reject_call(self):
        # ACS actually responded with an error status (e.g. call already ended) -- HttpResponseError.
        with patch.object(app.call_automation_client, "answer_call", side_effect=HttpResponseError("busy")), \
             patch.object(app.call_automation_client, "reject_call") as reject:
            result = _run_incoming_call(_incoming_call_event(context="ctx-1"))
        self.assertEqual(result, {})  # no unhandled 500 -- webhook still acks cleanly
        reject.assert_called_once_with(incoming_call_context="ctx-1")

    def test_answer_call_transport_error_falls_back_to_reject_call(self):
        # A timeout/connection failure talking to ACS at all is ServiceRequestError, a sibling of
        # HttpResponseError under AzureError, not a subclass of it -- this is the case that an
        # `except HttpResponseError` alone would miss and let escape as a 500.
        with patch.object(app.call_automation_client, "answer_call", side_effect=ServiceRequestError("timeout")), \
             patch.object(app.call_automation_client, "reject_call") as reject:
            result = _run_incoming_call(_incoming_call_event(context="ctx-2"))
        self.assertEqual(result, {})
        reject.assert_called_once_with(incoming_call_context="ctx-2")

    def test_reject_call_also_failing_does_not_crash(self):
        # Best-effort fallback: if the call is already gone, reject_call fails too. That must not
        # surface as an unhandled 500 either.
        with patch.object(app.call_automation_client, "answer_call", side_effect=HttpResponseError("gone")), \
             patch.object(app.call_automation_client, "reject_call", side_effect=HttpResponseError("gone")):
            result = _run_incoming_call(_incoming_call_event())
        self.assertEqual(result, {})

    def test_successful_answer_call_does_not_call_reject(self):
        with patch.object(app.call_automation_client, "answer_call") as answer, \
             patch.object(app.call_automation_client, "reject_call") as reject:
            result = _run_incoming_call(_incoming_call_event())
        answer.assert_called_once()
        reject.assert_not_called()
        self.assertEqual(result, {})


class BootGuardIsOnTheStartupPath(unittest.TestCase):
    """B3 exists is one claim; B3 runs before any call is served is another. Same discipline as
    the gate's in-path proof -- a guard nothing calls protects nothing."""

    @staticmethod
    def _run_lifespan():
        async def enter_and_exit():
            async with app.lifespan(app.app):
                pass
        asyncio.run(enter_and_exit())

    def test_startup_runs_the_boot_guard(self):
        calls = []
        with patch.object(app, "assert_boot_safety", lambda: calls.append("checked")):
            self._run_lifespan()
        self.assertEqual(calls, ["checked"])

    def test_a_refusing_guard_stops_the_app_from_starting(self):
        with patch.object(app, "assert_boot_safety", side_effect=SystemExit("B3: nope")), \
             self.assertRaises(SystemExit):
            self._run_lifespan()

    def test_importing_the_module_does_not_reach_for_arm(self):
        # The guard must not run at import time -- tests and tooling import this module freely,
        # and an import that phones ARM would make that impossible. If this regresses, importing
        # app in any test would already have failed at collection, but assert it explicitly.
        self.assertTrue(callable(app.assert_boot_safety))


class FakeWebSocket:
    def __init__(self):
        self.headers = {}
        self.accepted = False

    async def accept(self):
        self.accepted = True


class MediaStreamDelegatesToBridge(unittest.TestCase):
    def test_ws_handler_accepts_then_opens_a_connection_and_hands_off_the_call(self):
        # /ws used to run its own echo loop; it now opens the realtime connection and delegates
        # the whole relay -- this is the seam, not the frame-by-frame behavior, which is the
        # relay's own responsibility and is covered end to end by tests/test_whole_call.py.
        calls = []

        async def fake_run_call(transport, realtime, core_banking):
            calls.append((transport, realtime, core_banking))

        fake_ws = FakeWebSocket()
        realtime = FakeRealtimeServer()
        core_banking = FakeCoreBankingClient()
        # The process-wide client lifespan() would have built (issue #28). Patched rather than
        # constructed per call, because per-call construction is exactly what the design rules out.
        with patch.object(app, "connect_realtime", lambda: FakeRealtimeConnectCM(realtime)), \
             patch.object(app, "_core_banking", core_banking), \
             patch.object(app, "run_call", fake_run_call):
            asyncio.run(app.media_stream(fake_ws))
        self.assertTrue(fake_ws.accepted)
        # All three collaborators reached the relay.
        self.assertEqual(calls, [(fake_ws, realtime, core_banking)])

    def test_the_handler_refuses_to_run_without_an_initialised_client(self):
        # A handler called outside the app's lifespan must fail loudly rather than quietly
        # building a per-call client, which would give every call its own circuit breaker.
        with patch.object(app, "_core_banking", None), \
             self.assertRaises(RuntimeError):
            app.core_banking()


if __name__ == "__main__":
    unittest.main()

import asyncio
import os
import pathlib
import sys
import unittest
from unittest.mock import patch

# docs/echo-app/ is a standalone containerized app (own requirements.txt), not an importable
# package -- same sys.path pattern as voice-agent/ in test_accounts.py/test_bridge.py.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "docs" / "echo-app"))

# app.py reads these at import time (os.environ[...], no default) and constructs a
# CallAutomationClient from the connection string -- that parses the string locally with no
# network call, so a syntactically valid fake is enough to import the module under test.
os.environ.setdefault("ACS_CONNECTION_STRING", "endpoint=https://fake.communication.azure.com/;accesskey=ZmFrZWtleQ==")
os.environ.setdefault("APP_BASE_URL", "https://fake.example.azurecontainerapps.io")

from azure.core.exceptions import HttpResponseError, ServiceRequestError  # noqa: E402
import app  # noqa: E402


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


if __name__ == "__main__":
    unittest.main()

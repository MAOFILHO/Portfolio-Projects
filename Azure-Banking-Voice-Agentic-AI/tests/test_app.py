import asyncio
import os
import unittest
from unittest.mock import patch

# **No longer needed for the import itself** -- since 2026-09-11 `app` reads none of these at
# import time and builds no client at module scope (/code-review, 2026-09-11; pinned by
# `ImportingThisModuleHasNoSideEffects` below, which asserts it from a scrubbed subprocess). They
# stay set because the handler tests below drive `incoming_call`, which reads the base URL and
# asks for the ACS client the way a running app would. A syntactically valid fake connection
# string is enough: parsing one makes no network call.
os.environ.setdefault("ACS_CONNECTION_STRING", "endpoint=https://fake.communication.azure.com/;accesskey=ZmFrZWtleQ==")
os.environ.setdefault("APP_BASE_URL", "https://fake.example.azurecontainerapps.io")
# Read by lifespan() rather than at import, but the guard behind it has no default (issue #29) --
# so a test that exercises startup has to supply one, the same as a real deployment does.
os.environ.setdefault("CORE_BANKING_URL", "http://core-banking.test:8001")

from azbank_voice_agent import app
from azbank_voice_agent.call_records.fake import FakeCallRecordStore
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
    """The ACS client now lives where lifespan() puts it, so these install one first.

    Previously it was a module-level object these tests patched attributes on directly. It is
    built per test rather than once: `patch.object` restores what it replaced, but a client
    shared across tests would still be one process-wide object four tests mutate in turn.
    """

    def setUp(self):
        client = app.CallAutomationClient.from_connection_string(
            os.environ["ACS_CONNECTION_STRING"]
        )
        patcher = patch.object(app, "_call_automation", client)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_answer_call_http_error_falls_back_to_reject_call(self):
        # ACS actually responded with an error status (e.g. call already ended) -- HttpResponseError.
        with patch.object(app.call_automation(), "answer_call", side_effect=HttpResponseError("busy")), \
             patch.object(app.call_automation(), "reject_call") as reject:
            result = _run_incoming_call(_incoming_call_event(context="ctx-1"))
        self.assertEqual(result, {})  # no unhandled 500 -- webhook still acks cleanly
        reject.assert_called_once_with(incoming_call_context="ctx-1")

    def test_answer_call_transport_error_falls_back_to_reject_call(self):
        # A timeout/connection failure talking to ACS at all is ServiceRequestError, a sibling of
        # HttpResponseError under AzureError, not a subclass of it -- this is the case that an
        # `except HttpResponseError` alone would miss and let escape as a 500.
        with patch.object(app.call_automation(), "answer_call", side_effect=ServiceRequestError("timeout")), \
             patch.object(app.call_automation(), "reject_call") as reject:
            result = _run_incoming_call(_incoming_call_event(context="ctx-2"))
        self.assertEqual(result, {})
        reject.assert_called_once_with(incoming_call_context="ctx-2")

    def test_reject_call_also_failing_does_not_crash(self):
        # Best-effort fallback: if the call is already gone, reject_call fails too. That must not
        # surface as an unhandled 500 either.
        with patch.object(app.call_automation(), "answer_call", side_effect=HttpResponseError("gone")), \
             patch.object(app.call_automation(), "reject_call", side_effect=HttpResponseError("gone")):
            result = _run_incoming_call(_incoming_call_event())
        self.assertEqual(result, {})

    def test_successful_answer_call_does_not_call_reject(self):
        with patch.object(app.call_automation(), "answer_call") as answer, \
             patch.object(app.call_automation(), "reject_call") as reject:
            result = _run_incoming_call(_incoming_call_event())
        answer.assert_called_once()
        reject.assert_not_called()
        self.assertEqual(result, {})


class _ClosableStub:
    """Stands in for a collaborator lifespan() builds and closes. Not a fake in this project's
    sense -- the real fakes satisfy the protocols and these tests never call a protocol method."""

    async def aclose(self):
        pass


class _StubStoreFactory:
    """`TableStorageCallRecordStore` is used as a class with a classmethod constructor, so the
    stand-in has to answer that constructor rather than being callable."""

    @staticmethod
    def from_account_url(account_url, credential):
        return _ClosableStub()


class BootGuardIsOnTheStartupPath(unittest.TestCase):
    """B3 exists is one claim; B3 runs before any call is served is another. Same discipline as
    the gate's in-path proof -- a guard nothing calls protects nothing."""

    @staticmethod
    def _run_lifespan():
        """Enter and leave the lifespan with both clients stubbed out.

        The two collaborators lifespan() builds reach for real configuration and, for the store, for
        `azure-data-tables`. Neither is what these tests are about -- they are about B3 running
        before any call is served -- so both constructors are replaced. Patching them rather than
        setting environment variables keeps the test from asserting anything about configuration it
        is not testing.
        """
        async def enter_and_exit():
            async with app.lifespan(app.app):
                pass
        with patch.object(app, "HttpCoreBankingClient", lambda **kwargs: _ClosableStub()), \
             patch.object(app, "core_banking_url", lambda: "http://core-banking.test"), \
             patch.object(app, "TableStorageCallRecordStore", _StubStoreFactory()), \
             patch.object(app, "call_records_account_url", lambda: "https://storage.test"), \
             patch.object(app, "DefaultAzureCredential", lambda: None):
            asyncio.run(enter_and_exit())

    def test_startup_refuses_without_the_apps_own_base_url(self):
        """A missing `APP_BASE_URL` must kill the container, not the call.

        It used to, by accident: the value was read at module scope, so the import failed. Moving
        the read to call time (2026-09-11) fixed an import-time side effect and broke this at the
        same time -- nothing validated the variable at startup, `/healthz` answers `ok`
        unconditionally, and the first `KeyError` would have fired inside `incoming_call`. A
        misconfigured revision would have passed its health check, taken traffic, and failed in
        front of a caller, which is the precise inversion of the rule `boot.py` states in its own
        words (/code-review, 2026-09-11, Standards finding 1).
        """
        # B3 is patched out so the refusal under test is the only one that can fire -- otherwise
        # this would pass on the guard's own complaint about an unrelated variable.
        env = {k: v for k, v in os.environ.items() if k != "APP_BASE_URL"}
        with patch.object(app, "assert_boot_safety", lambda: None), \
             patch.dict(os.environ, env, clear=True), \
             self.assertRaises(SystemExit) as caught:
            self._run_lifespan()
        self.assertIn("APP_BASE_URL", str(caught.exception))

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

        async def fake_run_call(
            transport, realtime, core_banking, call_records, correlation_id=None, capture=None,
        ):
            calls.append((transport, realtime, core_banking, call_records, correlation_id))

        fake_ws = FakeWebSocket()
        realtime = FakeRealtimeServer()
        core_banking = FakeCoreBankingClient()
        call_records = FakeCallRecordStore()
        # The process-wide collaborators lifespan() would have built (issues #28, #48). Patched
        # rather than constructed per call, because per-call construction is exactly what the design
        # rules out -- a breaker thrown away with the call can never trip.
        with patch.object(app, "connect_realtime", lambda: FakeRealtimeConnectCM(realtime)), \
             patch.object(app, "_core_banking", core_banking), \
             patch.object(app, "_call_records", call_records), \
             patch.object(app, "run_call", fake_run_call):
            asyncio.run(app.media_stream(fake_ws))
        self.assertTrue(fake_ws.accepted)
        # All four collaborators reached the relay, and so did the correlation id -- which the
        # handler reads off the WebSocket's headers and hands in, rather than the relay fetching it.
        self.assertEqual(
            calls,
            [(fake_ws, realtime, core_banking, call_records, fake_ws.headers.get("x-ms-call-correlation-id"))],
        )

    def _id_handed_to_the_relay(self, header):
        handed = []

        async def fake_run_call(
            transport, realtime, core_banking, call_records, correlation_id=None, capture=None,
        ):
            handed.append(correlation_id)

        fake_ws = FakeWebSocket()
        fake_ws.headers = {"x-ms-call-correlation-id": header}
        with patch.object(app, "connect_realtime", lambda: FakeRealtimeConnectCM(FakeRealtimeServer())), \
             patch.object(app, "_core_banking", FakeCoreBankingClient()), \
             patch.object(app, "_call_records", FakeCallRecordStore()), \
             patch.object(app, "run_call", fake_run_call):
            asyncio.run(app.media_stream(fake_ws))
        return handed[0]

    def test_an_acs_correlation_id_reaches_the_relay_as_it_is(self):
        acs = "0f8fad5b-d9cb-469f-a165-70867728950e"
        self.assertEqual(self._id_handed_to_the_relay(acs), acs)

    def test_a_header_id_no_store_can_key_on_is_replaced_before_the_relay_sees_it(self):
        # The id is a Table RowKey (an escalation row is keyed on it from inside the relay) and a
        # Blob name, and the header is the carrier's to set. `#`, `?`, a path separator or an
        # absurd length must cost the call its ACS id, never its escalation or summary row.
        for bad in ("bad#id?x", "a/b", "back\\slash", "x" * 5000, "has space"):
            handed = self._id_handed_to_the_relay(bad)
            self.assertNotEqual(handed, bad)
            self.assertRegex(handed, r"^[A-Za-z0-9._-]{1,128}$")

    def test_the_replacement_is_not_logged_with_the_raw_id(self):
        with self.assertLogs(level="INFO") as logs:
            self._id_handed_to_the_relay("bad#id?x")
        self.assertNotIn("bad#id?x", "\n".join(logs.output))

    def test_the_handler_refuses_to_run_without_an_initialised_store(self):
        # The same rule the core-banking client already has, for the same reason: a store built on
        # first use would be built per call, and a per-call store is one whose failures nobody
        # accumulates.
        with patch.object(app, "_call_records", None), \
             self.assertRaises(RuntimeError):
            app.call_records()

    def test_the_handler_refuses_to_run_without_an_initialised_client(self):
        # A handler called outside the app's lifespan must fail loudly rather than quietly
        # building a per-call client, which would give every call its own circuit breaker.
        with patch.object(app, "_core_banking", None), \
             self.assertRaises(RuntimeError):
            app.core_banking()

    def test_the_handler_refuses_to_run_without_an_initialised_call_automation_client(self):
        with patch.object(app, "_call_automation", None), \
             self.assertRaises(RuntimeError):
            app.call_automation()


class PostCallIsScheduledAfterTheCallNeverInsideIt(unittest.TestCase):
    """Phase 8 exit criterion 4 at the entry point: the handler hands the finished call's capture to
    a background task and returns. It never awaits the pipeline, on any path out of the handler."""

    @staticmethod
    def _drive(run_call_impl=None, run_closed_call_impl=None, budget=None, postcall_impl=None):
        """Run one /ws call with everything stubbed; return (post-call invocations, handler done?)."""
        invocations = []

        async def fake_postcall(capture, services):
            invocations.append((capture, services))
            if postcall_impl is not None:
                await postcall_impl()

        async def default_run_call(*args, capture=None, **kwargs):
            capture.finish("corr-x", "model_ended", "anonymous", 1, 10)

        async def default_budget(_records):
            return None

        async def main():
            await app.media_stream(FakeWebSocket())
            handler_returned = True
            # Only now let any scheduled task run to completion (or stay blocked, if it is one that
            # never finishes) so the test can look at it.
            pending = list(app._postcall_tasks)
            await asyncio.wait(pending, timeout=0.05)
            for task in pending:
                task.cancel()
            return handler_returned

        with patch.object(app, "connect_realtime", lambda: FakeRealtimeConnectCM(FakeRealtimeServer())), \
             patch.object(app, "_core_banking", FakeCoreBankingClient()), \
             patch.object(app, "_call_records", FakeCallRecordStore()), \
             patch.object(app, "budget_or_closed", budget or default_budget), \
             patch.object(app, "run_call", run_call_impl or default_run_call), \
             patch.object(app, "run_closed_call", run_closed_call_impl), \
             patch.object(app, "run_postcall", fake_postcall):
            returned = asyncio.run(main())
        return invocations, returned

    def test_a_finished_call_hands_its_capture_to_the_pipeline_once(self):
        invocations, _ = self._drive()
        self.assertEqual(len(invocations), 1)
        capture, services = invocations[0]
        self.assertEqual(capture.end_reason, "model_ended")
        self.assertIsInstance(services, app.PostcallServices)

    def test_the_handler_returns_while_the_pipeline_is_still_running(self):
        never = asyncio.Event()

        async def blocks_forever():
            await never.wait()

        invocations, returned = self._drive(postcall_impl=blocks_forever)
        self.assertTrue(returned)
        self.assertEqual(len(invocations), 1)

    def test_a_call_that_raises_still_schedules_the_pipeline(self):
        async def crashes(*args, capture=None, **kwargs):
            raise RuntimeError("relay failed")

        async def main():
            with self.assertRaises(RuntimeError):
                await app.media_stream(FakeWebSocket())
            pending = list(app._postcall_tasks)
            if pending:
                await asyncio.wait(pending, timeout=0.05)

        invocations = []

        async def fake_postcall(capture, services):
            invocations.append(capture)

        async def no_budget_problem(_records):
            return None

        with patch.object(app, "connect_realtime", lambda: FakeRealtimeConnectCM(FakeRealtimeServer())), \
             patch.object(app, "_core_banking", FakeCoreBankingClient()), \
             patch.object(app, "_call_records", FakeCallRecordStore()), \
             patch.object(app, "budget_or_closed", no_budget_problem), \
             patch.object(app, "run_call", crashes), \
             patch.object(app, "run_postcall", fake_postcall):
            asyncio.run(main())
        self.assertEqual(len(invocations), 1)

    def _drive_a_connect_that_raises(self, budget=None):
        """Run one /ws call whose realtime connection cannot be opened, through the real pipeline
        (no adapters configured, so only the row is written); return the store it wrote to."""
        class Refuses:
            async def __aenter__(self):
                raise ConnectionError("realtime endpoint unreachable")

            async def __aexit__(self, *exc_info):
                return False

        async def no_budget_problem(_records):
            return None

        records = FakeCallRecordStore()

        async def main():
            with self.assertRaises(ConnectionError):
                await app.media_stream(FakeWebSocket())
            pending = list(app._postcall_tasks)
            if pending:
                await asyncio.wait(pending, timeout=1)

        with patch.object(app, "connect_realtime", lambda: Refuses()), \
             patch.object(app, "_core_banking", FakeCoreBankingClient()), \
             patch.object(app, "_call_records", records), \
             patch.object(app, "budget_or_closed", budget or no_budget_problem), \
             patch.object(app, "_redactor", None), \
             patch.object(app, "_summarizer", None), \
             patch.object(app, "_transcripts", None):
            asyncio.run(main())
        return records

    def test_a_call_whose_realtime_connection_cannot_be_opened_still_gets_its_row(self):
        # Exit criterion 2: one row per completed call. The relay never ran, so nothing finished the
        # capture; the handler does, as an error the caller never got past.
        records = self._drive_a_connect_that_raises()
        self.assertEqual(len(records.call_summaries), 1)
        row = records.call_summaries[0]
        self.assertEqual(row.call_outcome, "error")
        self.assertEqual(row.end_reason, "error")
        self.assertEqual(row.auth_state, "anonymous")
        self.assertEqual(row.turn_count, 0)
        self.assertEqual(row.transcript_status, "none")

    def test_the_closed_path_whose_connection_cannot_be_opened_gets_its_row_too(self):
        from azbank_voice_agent.cost import caps

        async def spent(_records):
            raise caps.DailyBudgetSpent("budget", cause=caps.CLOSED_PATH_BUDGET_SPENT)

        records = self._drive_a_connect_that_raises(budget=spent)
        self.assertEqual([r.call_outcome for r in records.call_summaries], ["error"])

    def test_a_closed_call_gets_a_pipeline_run_too(self):
        from azbank_voice_agent.cost import caps

        async def spent(_records):
            raise caps.DailyBudgetSpent("budget", cause=caps.CLOSED_PATH_BUDGET_SPENT)

        async def closed_call(transport, realtime, call_records, correlation_id=None,
                              closed_path_cause=None, capture=None, **kwargs):
            capture.finish(correlation_id, "closed", "anonymous", 0, 5)

        invocations, _ = self._drive(budget=spent, run_closed_call_impl=closed_call)
        self.assertEqual([c.end_reason for c, _ in invocations], ["closed"])

    def test_a_failure_to_schedule_never_reaches_the_caller(self):
        async def main():
            with patch.object(app, "_call_records", None):
                app._schedule_postcall(app.CallCapture())

        asyncio.run(main())


class ImportingThisModuleHasNoSideEffects(unittest.TestCase):
    """The rule the other three modules state and follow, finally true of the entry point too.

    `mock-core-banking/azbank_core_banking/app.py` ("Importing this module must not open a
    database or create a file"), `boot.py` ("deliberately not at import time") and
    `realtime/client.py` ("Reads configuration at call time, not import time") all say it. This
    module was the sibling deployable's entry point in the same role, and until 2026-09-11 it read
    two environment variables with `os.environ[...]` and built a live `CallAutomationClient` at
    module scope (/code-review, 2026-09-11).

    A subprocess with a scrubbed environment, because the import already happened at the top of
    this file with the variables set -- nothing in-process can un-import it, and a test that
    merely reloaded the module would still be running under an environment that has them.
    """

    def test_it_imports_with_none_of_its_configuration_set(self):
        import subprocess
        import sys

        env = {
            k: v for k, v in os.environ.items()
            if k not in ("ACS_CONNECTION_STRING", "APP_BASE_URL", "CORE_BANKING_URL",
                         "CALL_RECORDS_ACCOUNT_URL", "AOAI_DEPLOYMENT")
        }
        result = subprocess.run(
            [sys.executable, "-c", "import azbank_voice_agent.app"],
            capture_output=True, text=True, env=env,
        )
        self.assertEqual(
            result.returncode, 0,
            f"importing the entry point needed configuration:\n{result.stderr}",
        )


class _AsyncCredentialStub:
    closed = False

    async def close(self):
        type(self).closed = True


class PostCallAdaptersAreBuiltFromConfigurationAndNeverBlockBoot(unittest.TestCase):
    """Phase 8: the redactor and summariser exist only when their configuration does, and a missing
    value switches one feature off -- it never stops the app starting, because post-call work must
    never be able to stop a call. Inspected from *inside* the lifespan, where the process-wide
    collaborators are live."""

    @staticmethod
    def _inside_lifespan(env):
        from azbank_voice_agent.postcall.language import LanguagePIIRedactor
        from azbank_voice_agent.postcall.summarizer import OpenAISummarizer

        seen = {}
        _AsyncCredentialStub.closed = False

        async def go():
            async with app.lifespan(app.app):
                seen["redactor"] = app._redactor
                seen["summarizer"] = app._summarizer
                seen["types"] = (LanguagePIIRedactor, OpenAISummarizer)
            seen["after"] = (app._redactor, app._summarizer)

        clean = {k: v for k, v in os.environ.items()
                 if k not in ("LANGUAGE_ENDPOINT", "AOAI_TEXT_DEPLOYMENT", "AOAI_ENDPOINT",
                              "TRANSCRIPTS_ACCOUNT_URL")}
        with patch.object(app, "assert_boot_safety", lambda: None), \
             patch.object(app, "HttpCoreBankingClient", lambda **kwargs: _ClosableStub()), \
             patch.object(app, "core_banking_url", lambda: "http://core-banking.test"), \
             patch.object(app, "TableStorageCallRecordStore", _StubStoreFactory()), \
             patch.object(app, "call_records_account_url", lambda: "https://storage.test"), \
             patch.object(app, "DefaultAzureCredential", lambda: None), \
             patch.object(app, "AsyncDefaultAzureCredential", _AsyncCredentialStub), \
             patch.object(app, "get_bearer_token_provider", lambda credential, scope: (lambda: None)), \
             patch.dict(os.environ, {**clean, **env}, clear=True):
            asyncio.run(go())
        return seen

    def test_unconfigured_means_neither_adapter_and_no_credential_is_built(self):
        seen = self._inside_lifespan({})
        self.assertIsNone(seen["redactor"])
        self.assertIsNone(seen["summarizer"])
        self.assertFalse(_AsyncCredentialStub.closed)

    def test_a_language_endpoint_builds_the_redactor_only(self):
        seen = self._inside_lifespan({"LANGUAGE_ENDPOINT": "https://lang.cognitiveservices.azure.com/"})
        self.assertIsInstance(seen["redactor"], seen["types"][0])
        self.assertIsNone(seen["summarizer"])

    def test_a_text_deployment_and_an_openai_endpoint_build_the_summarizer(self):
        seen = self._inside_lifespan({"AOAI_TEXT_DEPLOYMENT": "gpt-5.4-mini",
                                      "AOAI_ENDPOINT": "https://aoai.openai.azure.com/"})
        self.assertIsInstance(seen["summarizer"], seen["types"][1])
        self.assertIsNone(seen["redactor"])

    def test_a_text_deployment_with_no_openai_endpoint_switches_summaries_off_without_failing(self):
        seen = self._inside_lifespan({"AOAI_TEXT_DEPLOYMENT": "gpt-5.4-mini"})
        self.assertIsNone(seen["summarizer"])

    def test_shutdown_clears_the_adapters_and_closes_the_credential(self):
        seen = self._inside_lifespan({"LANGUAGE_ENDPOINT": "https://lang.cognitiveservices.azure.com/"})
        self.assertEqual(seen["after"], (None, None))
        self.assertTrue(_AsyncCredentialStub.closed)

    def test_a_malformed_language_endpoint_is_refused_at_boot_not_at_the_first_call(self):
        with self.assertRaises(SystemExit):
            self._inside_lifespan({"LANGUAGE_ENDPOINT": "Endpoint=https://x;Key=abc"})


if __name__ == "__main__":
    unittest.main()

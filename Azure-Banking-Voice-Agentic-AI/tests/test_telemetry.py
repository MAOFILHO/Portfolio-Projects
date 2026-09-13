"""Phase 6 (Observability, issue #61): the OTel seam, the D15 allowlist, fail-open, and D13's
closed-path distinction.

Rides the four existing fakes exactly as `docs/phase6/exit-criteria.md` D17 requires -- no new test
double is added here. `tests/telemetry_harness.py` is a *helper*, not a fake: it wires the real
`telemetry.build_tracer_provider` factory to an in-memory exporter and reads back what a fake-call
run actually produced.

**Why several small traced runs rather than one big scripted call.** The allowlist-exactness check
needs every attribute value this project's own code can produce to appear at least once (D17: "the
set of attribute keys ... is exactly the D15 table, no more, no less"), and several of those values
are mutually exclusive on one `FakeCoreBankingClient` (its own `fail_with` answers *every* call,
authentication included -- see `core_banking/fake.py`'s `_check`). Calling `dispatch_tool_call`
directly for each outcome class is also simply the more direct test: it is the seam
`docs/phase4/exit-criteria.md`'s own B1 suite already drives the same way
(`tests/test_gate.py::EveryDeclaredToolIsBehindTheGate`).
"""
import asyncio
import json
import socket
import unittest

from azbank_voice_agent.call_records.fake import FakeCallRecordStore
from azbank_voice_agent.core_banking import CoreBankingUnavailable
from azbank_voice_agent.core_banking import client as core_banking_client
from azbank_voice_agent.core_banking.fake import DEFAULT_PIN, FakeCoreBankingClient
from azbank_voice_agent.cost import caps
from azbank_voice_agent.dispatch import gate
from azbank_voice_agent.dispatch.tools import CallScope, dispatch_tool_call
from azbank_voice_agent.observability import telemetry
from azbank_voice_agent.realtime import session as session_module
from azbank_voice_agent.realtime.fake import FakeRealtimeServer, audio_delta, function_call, response_done
from azbank_voice_agent.realtime.session import run_call, run_closed_call
from azbank_voice_agent.transport.fake import FakeTransport, audio_frame, dtmf_frame
from opentelemetry.sdk.metrics.export import InMemoryMetricReader
from opentelemetry.sdk.trace.export import SpanExporter, SpanExportResult
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

try:
    # `make test` runs `unittest discover -s tests`, which puts this directory on sys.path.
    from telemetry_harness import run_traced_call
except ImportError:
    # `python -m unittest tests.test_telemetry` does not. Same fallback tests/test_redteam.py uses
    # for tests/redteam_harness.py.
    from tests.telemetry_harness import run_traced_call


def _keyed(pin):
    return [dtmf_frame(digit) for digit in pin]


class AllowlistSpanProcessorDropsAnythingNotOnTheTable(unittest.TestCase):
    """D9's filter, tested directly, before any fake call is involved -- fast and deterministic."""

    def test_an_unlisted_attribute_is_dropped_and_a_listed_one_survives(self):
        exporter = InMemorySpanExporter()
        provider = telemetry.build_tracer_provider(exporter)
        with provider.get_tracer("test").start_as_current_span(telemetry.CALL) as span:
            span.set_attribute("correlation_id", "corr-1")  # on the table
            span.set_attribute("nonsense", "should not survive")  # not on the table
        provider.force_flush()
        [collected] = exporter.get_finished_spans()
        self.assertEqual(dict(collected.attributes), {"correlation_id": "corr-1"})

    def test_a_span_with_an_unrecognised_name_keeps_no_attribute_at_all(self):
        # Deny-by-default applies to a span kind this table has not named exactly as it applies to
        # an attribute key it has not named -- see telemetry.ALLOWLIST's own module comment.
        exporter = InMemorySpanExporter()
        provider = telemetry.build_tracer_provider(exporter)
        with provider.get_tracer("test").start_as_current_span("mystery_span") as span:
            span.set_attribute("anything", "at all")
        provider.force_flush()
        [collected] = exporter.get_finished_spans()
        self.assertEqual(dict(collected.attributes), {})

    def test_values_are_never_inspected_only_keys(self):
        # D9: "a scrubber has to be right about every attribute every future instrumentation adds;
        # a key allowlist cannot." A value that looks exactly like a PIN survives on an allowed key
        # -- the filter's job stops at the name, and B2's own scan (elsewhere in this suite) is
        # what has to hold given that.
        exporter = InMemorySpanExporter()
        provider = telemetry.build_tracer_provider(exporter)
        with provider.get_tracer("test").start_as_current_span(telemetry.CALL) as span:
            span.set_attribute("correlation_id", DEFAULT_PIN)
        provider.force_flush()
        [collected] = exporter.get_finished_spans()
        self.assertEqual(collected.attributes["correlation_id"], DEFAULT_PIN)


class _Recorder:
    """A minimal `httpx.MockTransport` handler -- the same shape
    `tests/test_core_banking_client.py`'s own `Recorder` uses, kept local rather than imported
    because that one is a private test-module helper, not a shared one."""

    def __init__(self, *responses):
        self._responses = list(responses)

    def __call__(self, request):
        return self._responses.pop(0)


def _json_response(payload, status=200):
    import httpx
    return httpx.Response(status, json=payload)


class CoreBankingSpanAttributesMatchTheAllowlist(unittest.TestCase):
    """The "core banking" span only exists on `HttpCoreBankingClient` -- no fake-call test ever
    exercises it, because every one of them runs against `FakeCoreBankingClient`, which makes no
    HTTP request at all. Tested directly against `httpx.MockTransport`, the same way
    `tests/test_core_banking_client.py` already tests this client's own behaviour.
    """

    def test_a_successful_get_and_a_404_produce_exactly_the_table(self):
        import httpx

        client = core_banking_client.HttpCoreBankingClient(
            base_url="http://core-banking.test",
            transport=httpx.MockTransport(_Recorder(
                _json_response({"balance_cents": 240000}),
                _json_response({"detail": {"account": "bitcoin"}}, status=404),
            )),
        )
        exporter = InMemorySpanExporter()
        telemetry.configure(tracer_provider=telemetry.build_tracer_provider(exporter))
        try:
            asyncio.run(client.get_balance("chequing"))
            with self.assertRaises(core_banking_client.UnknownAccountError):
                asyncio.run(client.get_balance("bitcoin"))
        finally:
            telemetry.tracer_provider().force_flush()
            telemetry.configure()

        spans = exporter.get_finished_spans()
        core_banking_spans = [s for s in spans if s.name == telemetry.CORE_BANKING]
        self.assertEqual(len(core_banking_spans), 2)
        keys = set().union(*(s.attributes.keys() for s in core_banking_spans))
        self.assertEqual(keys, telemetry.ALLOWLIST[telemetry.CORE_BANKING])
        # The template, not the rendered path -- no account name on either span.
        for span in core_banking_spans:
            with self.subTest(status=span.attributes.get("status_code")):
                self.assertEqual(span.attributes["route_template"], "/accounts/{account}")
                self.assertEqual(span.attributes["http_method"], "GET")
        self.assertEqual(
            {s.attributes["status_code"] for s in core_banking_spans}, {200, 404}
        )


class AllowlistExactnessAcrossTheOtherThreeSpans(unittest.TestCase):
    """D17 criterion 1: the set of attribute keys across every collected span equals the D15 table
    exactly, per span name -- no more, no less. Assembled from several small, targeted runs (see
    module docstring) rather than one script, so every mutually-exclusive outcome the real code can
    produce actually gets exercised once."""

    def _collect(self):
        spans = []

        # gate_decision: denied -- anonymous call, no auth.
        anon_scope = CallScope(core_banking=FakeCoreBankingClient(), call_records=FakeCallRecordStore())
        spans += run_traced_call(dispatch_tool_call(
            "get_balance", '{"account": "chequing"}', gate.BANKING_AGENT, gate.ANONYMOUS, scope=anon_scope,
        ))

        # gate_decision: allowed, no outcome_class -- an ordinary success.
        ok_scope = CallScope(core_banking=FakeCoreBankingClient(), call_records=FakeCallRecordStore())
        spans += run_traced_call(dispatch_tool_call(
            "get_balance", '{"account": "chequing"}', gate.BANKING_AGENT, gate.AUTHENTICATED, scope=ok_scope,
        ))

        # outcome_class: unknown_account
        unknown_scope = CallScope(core_banking=FakeCoreBankingClient(), call_records=FakeCallRecordStore())
        spans += run_traced_call(dispatch_tool_call(
            "get_balance", '{"account": "bitcoin"}', gate.BANKING_AGENT, gate.AUTHENTICATED,
            scope=unknown_scope,
        ))

        # outcome_class: malformed
        malformed_scope = CallScope(core_banking=FakeCoreBankingClient(), call_records=FakeCallRecordStore())
        spans += run_traced_call(dispatch_tool_call(
            "get_balance", '{"account": {}}', gate.BANKING_AGENT, gate.AUTHENTICATED, scope=malformed_scope,
        ))

        # outcome_class: unavailable
        down_scope = CallScope(
            core_banking=FakeCoreBankingClient(fail_with=CoreBankingUnavailable("down")),
            call_records=FakeCallRecordStore(),
        )
        spans += run_traced_call(dispatch_tool_call(
            "get_balance", '{"account": "chequing"}', gate.BANKING_AGENT, gate.AUTHENTICATED, scope=down_scope,
        ))

        # outcome_class: declined -- more than the caller has.
        declined_scope = CallScope(core_banking=FakeCoreBankingClient(), call_records=FakeCallRecordStore())
        spans += run_traced_call(dispatch_tool_call(
            "transfer",
            '{"from_account": "chequing", "to_account": "savings", "amount": 999999}',
            gate.BANKING_AGENT, gate.AUTHENTICATED, scope=declined_scope,
        ))

        # A whole call, for the "call" and "turn" spans: one turn with no audio (tool-call-only,
        # agent_spoke False) and one with audio (agent_spoke True), ending when the model's
        # scripted events run out (end_reason "model_ended").
        transport = FakeTransport(frames=[audio_frame("hello")], hang=True)
        realtime = FakeRealtimeServer(
            events=[
                function_call("get_balance", '{"account": "chequing"}'),
                response_done(),
                audio_delta("here-you-go"),
                response_done(),
            ],
            respond_after_appends=1,
        )
        spans += run_traced_call(
            run_call(transport, realtime, FakeCoreBankingClient(), FakeCallRecordStore())
        )

        # The closed path, for closed_path_taken/closed_path_cause on the "call" span.
        for cause in (caps.CLOSED_PATH_BUDGET_SPENT, caps.CLOSED_PATH_LEDGER_UNREADABLE):
            closed_transport = FakeTransport(frames=[audio_frame("hi")], hang=True)
            closed_realtime = FakeRealtimeServer(
                events=[audio_delta("were-closed"), response_done()], respond_after_appends=0,
            )
            spans += run_traced_call(run_closed_call(
                closed_transport, closed_realtime, FakeCallRecordStore(), closed_path_cause=cause,
            ))

        return spans

    def test_every_span_kinds_attribute_keys_are_exactly_the_table(self):
        by_name = {}
        for span in self._collect():
            by_name.setdefault(span.name, set()).update(span.attributes.keys())

        for name, allowed in telemetry.ALLOWLIST.items():
            with self.subTest(span=name):
                if name == telemetry.CORE_BANKING:
                    # Covered by CoreBankingSpanAttributesMatchTheAllowlist above -- no fake-call
                    # path ever produces this span (see that class's own docstring).
                    continue
                self.assertEqual(
                    by_name.get(name, set()), set(allowed),
                    f"{name!r} span attributes are not exactly the D15 table",
                )

    def test_outcome_classes_are_exactly_the_glossarys_four(self):
        outcome_classes = {
            span.attributes["outcome_class"]
            for span in self._collect()
            if span.name == telemetry.TOOL_CALL and "outcome_class" in span.attributes
        }
        self.assertEqual(
            outcome_classes,
            {
                telemetry.OUTCOME_UNKNOWN_ACCOUNT, telemetry.OUTCOME_MALFORMED,
                telemetry.OUTCOME_UNAVAILABLE, telemetry.OUTCOME_DECLINED,
            },
        )


class TelemetryFailsOpen(unittest.TestCase):
    """D11/D14: an unreachable or erroring exporter never raises into the call path, never delays
    a turn, and never changes the call's outcome. `BatchSpanProcessor.on_end` only enqueues -- the
    export itself runs on a background thread that swallows every exception the exporter raises
    (`opentelemetry.sdk._shared_internal.BatchProcessor._export`, pinned SDK release verified
    2026-09-13). Each test forces a flush after the call (`force_flush`, not the batch's default
    5-second schedule delay) so `export()` actually runs within the test and each `export_attempted`
    flag proves the raising/refusing branch really executed -- otherwise a no-op exporter would pass
    these tests identically, which is exactly the gap a 2026-09-13 review of issue #61 found."""

    def _run_a_normal_call(self):
        transport, realtime = self._scripted_call()
        asyncio.run(run_call(transport, realtime, FakeCoreBankingClient(), FakeCallRecordStore()))
        return transport

    def _scripted_call(self):
        transport = FakeTransport(frames=[audio_frame("hello")], hang=True)
        realtime = FakeRealtimeServer(
            events=[audio_delta("agent-says-hi"), response_done()], respond_after_appends=1,
        )
        return transport, realtime

    def test_the_call_completes_normally_with_an_exporter_that_always_raises(self):
        export_attempted = []

        class _AlwaysRaises(SpanExporter):
            def export(self, spans):
                export_attempted.append(1)
                raise RuntimeError("this exporter always fails")

            def shutdown(self):
                pass

            def force_flush(self, timeout_millis=30000):
                return True

        provider = telemetry.build_tracer_provider(_AlwaysRaises())
        telemetry.configure(tracer_provider=provider)
        self.addCleanup(telemetry.configure)
        transport = self._run_a_normal_call()
        provider.force_flush()
        self.assertEqual(transport.sent_audio_payloads, ["agent-says-hi"])
        self.assertTrue(export_attempted, "export() never ran -- this test proved nothing about raising")

    def test_the_call_completes_normally_with_an_exporter_that_refuses_connections(self):
        # A real refusal, not a simulated one: port 1 is not listened on, so connect() raises
        # ConnectionRefusedError immediately -- the literal "refuses connection" issue #61 asks for.
        export_attempted = []

        class _RefusesConnections(SpanExporter):
            def export(self, spans):
                export_attempted.append(1)
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.settimeout(1.0)
                    s.connect(("127.0.0.1", 1))
                return SpanExportResult.SUCCESS  # unreachable -- connect() above always raises

            def shutdown(self):
                pass

            def force_flush(self, timeout_millis=30000):
                return True

        provider = telemetry.build_tracer_provider(_RefusesConnections())
        telemetry.configure(tracer_provider=provider)
        self.addCleanup(telemetry.configure)
        transport = self._run_a_normal_call()
        provider.force_flush()
        self.assertEqual(transport.sent_audio_payloads, ["agent-says-hi"])
        self.assertTrue(
            export_attempted, "export() never ran -- this test proved nothing about a refused connection"
        )


class NoConstraintIsEnforcedByTelemetry(unittest.TestCase):
    """D11's corollary, by direct comparison. Every other suite in this project (`test_gate.py`,
    `test_zz_b2_leak_scan.py`, `test_whole_call.py`'s B4 cap tests) already proves this by
    construction -- nothing in them ever calls `telemetry.configure()` at all, so they run with
    telemetry absent as their only mode. This class proves the same property the other direction:
    the two behaviours telemetry sits directly next to (a gate refusal, a cost cap tripping) are
    identical whether or not telemetry happens to be configured.
    """

    def _refusal(self):
        scope = CallScope(core_banking=FakeCoreBankingClient(), call_records=FakeCallRecordStore())
        return asyncio.run(dispatch_tool_call(
            "get_balance", '{"account": "chequing"}', gate.BANKING_AGENT, gate.ANONYMOUS, scope=scope,
        ))

    def test_a_gate_refusal_is_identical_with_telemetry_configured_or_absent(self):
        telemetry.configure()  # the explicit no-op default
        without_telemetry = self._refusal()

        telemetry.configure(tracer_provider=telemetry.build_tracer_provider(InMemorySpanExporter()))
        try:
            with_telemetry = self._refusal()
        finally:
            telemetry.configure()

        self.assertEqual(without_telemetry, with_telemetry)
        self.assertEqual(json.loads(without_telemetry), {"error": gate.REFUSAL})

    def _tripped_turn_count(self):
        from unittest.mock import patch

        transport = FakeTransport(frames=[audio_frame("hi")], hang=True)
        realtime = FakeRealtimeServer(events=[response_done()] * 5, respond_after_appends=0, hang=True)
        with patch.object(caps, "MAX_CALL_TURNS", 2):
            asyncio.run(run_call(transport, realtime, FakeCoreBankingClient(), FakeCallRecordStore()))
        return realtime.consumed

    def test_b4s_turn_cap_trips_identically_with_telemetry_configured_or_absent(self):
        telemetry.configure()
        without_telemetry = self._tripped_turn_count()

        telemetry.configure(tracer_provider=telemetry.build_tracer_provider(InMemorySpanExporter()))
        try:
            with_telemetry = self._tripped_turn_count()
        finally:
            telemetry.configure()

        self.assertEqual(without_telemetry, with_telemetry)
        self.assertEqual(without_telemetry, 2)  # the patched cap, not a coincidence


class ClosedPathCauseIsDistinguished(unittest.TestCase):
    """D13: budget-spent and ledger-unreadable are opposites in telemetry despite being one
    sentence to the caller. The span differs; what the caller hears does not."""

    def _closed_call(self, cause):
        transport = FakeTransport(frames=[audio_frame("hi")], hang=True)
        realtime = FakeRealtimeServer(
            events=[audio_delta("were-closed"), response_done()], respond_after_appends=0,
        )
        spans = run_traced_call(
            run_closed_call(transport, realtime, FakeCallRecordStore(), closed_path_cause=cause)
        )
        call_span = next(s for s in spans if s.name == telemetry.CALL)
        return call_span, realtime

    def _spoken_notes(self, realtime):
        return [
            part["text"]
            for message in realtime.sent
            if message["type"] == "conversation.item.create"
            and message["item"].get("type") == "message"
            for part in message["item"]["content"]
        ]

    def test_the_two_causes_differ_in_the_span_but_the_caller_hears_the_same_sentence(self):
        budget_span, budget_realtime = self._closed_call(caps.CLOSED_PATH_BUDGET_SPENT)
        unreadable_span, unreadable_realtime = self._closed_call(caps.CLOSED_PATH_LEDGER_UNREADABLE)

        self.assertEqual(budget_span.attributes["closed_path_cause"], caps.CLOSED_PATH_BUDGET_SPENT)
        self.assertEqual(
            unreadable_span.attributes["closed_path_cause"], caps.CLOSED_PATH_LEDGER_UNREADABLE
        )
        self.assertNotEqual(
            budget_span.attributes["closed_path_cause"], unreadable_span.attributes["closed_path_cause"]
        )
        self.assertTrue(budget_span.attributes["closed_path_taken"])
        self.assertTrue(unreadable_span.attributes["closed_path_taken"])

        spoken = self._spoken_notes(budget_realtime)
        self.assertEqual(spoken, self._spoken_notes(unreadable_realtime))
        self.assertEqual(spoken, [session_module.CLOSED])


class MetricsRecordB4AndB5(unittest.TestCase):
    """D14: B4's daily minutes and B5's turn latency exist as metrics, not reconstructed from spans."""

    def setUp(self):
        self.reader = InMemoryMetricReader()
        telemetry.configure(meter_provider=telemetry.build_meter_provider(self.reader))
        self.addCleanup(telemetry.configure)

    def _metric(self, name):
        for rm in self.reader.get_metrics_data().resource_metrics:
            for sm in rm.scope_metrics:
                for metric in sm.metrics:
                    if metric.name == name:
                        return metric
        return None

    def test_daily_minutes_accumulate_as_a_counter(self):
        telemetry.record_daily_minutes(2.0)
        telemetry.record_daily_minutes(3.0)
        metric = self._metric("b4.daily_minutes_used")
        self.assertEqual(sum(dp.value for dp in metric.data.data_points), 5.0)

    def test_turn_latency_records_as_a_histogram(self):
        telemetry.record_turn_latency(0.5)
        metric = self._metric("b5.turn_latency_seconds")
        self.assertEqual(sum(dp.count for dp in metric.data.data_points), 1)

    def test_a_whole_call_records_both_metrics(self):
        transport = FakeTransport(frames=[audio_frame("hello")], hang=True)
        realtime = FakeRealtimeServer(
            events=[audio_delta("hi-there"), response_done()], respond_after_appends=1,
        )
        asyncio.run(run_call(transport, realtime, FakeCoreBankingClient(), FakeCallRecordStore()))
        self.assertIsNotNone(self._metric("b4.daily_minutes_used"))


class TelemetryDefaultsToNoOp(unittest.TestCase):
    """D11: before `configure()` is ever called, and again after calling it with no arguments,
    every function in this module is a safe no-op -- zero overhead, and nothing to fail open from
    because nothing is wired at all."""

    def test_tracer_and_meter_work_with_nothing_configured(self):
        telemetry.configure()
        span = telemetry.tracer().start_span("whatever")
        span.set_attribute("x", "y")
        span.end()  # must not raise
        telemetry.meter().create_counter("c").add(1)  # must not raise
        telemetry.record_daily_minutes(1.0)
        telemetry.record_turn_latency(0.1)


if __name__ == "__main__":
    unittest.main()

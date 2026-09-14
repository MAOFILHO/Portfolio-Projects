"""Shared helper for Phase 6's span-collecting tests (issue #61).

Not a test module -- imported by `test_telemetry.py`, `test_b2_content_recording.py` and
`test_zz_b2_leak_scan.py`, the same way `redteam_harness.py` and `keyed_values.py` are imported
rather than discovered (see `tests/keyed_values.py`'s own docstring for that convention).
"""
import asyncio

from azbank_voice_agent.observability import telemetry
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter


def run_traced_call(coro, correlation_id="corr-test", connection_id="conn-test"):
    """Run one already-built coroutine inside a fresh "call" span, with an in-memory exporter
    attached for the duration, and return every span it produced.

    Goes through `telemetry.build_tracer_provider` -- the real production factory, allowlist
    processor included -- rather than a test-local `TracerProvider`, so these tests exercise the
    same filtering path a real exporter would sit behind. `force_flush()` after the call ends is
    what makes the spans available without waiting on `BatchSpanProcessor`'s own schedule (see that
    function's docstring for why production always uses the batch processor rather than the
    synchronous one).

    `correlation_id`/`connection_id` are set on the span here because `app.py`'s `media_stream` is
    what sets them in production, and nothing under test here is `app.py` -- this harness is
    standing in for that one part of it, the same way a fake stands in for a collaborator.

    **Telemetry is reset to the no-op default in a `finally`, unconditionally.** `telemetry.
    configure()` is a process-wide slot (see `observability/telemetry.py`'s module docstring) --
    swapping it mid-run is a thing only tests do, and a test that raised before resetting it would
    leak its in-memory exporter into whatever test happens to run next in the same process.
    """
    exporter = InMemorySpanExporter()
    telemetry.configure(tracer_provider=telemetry.build_tracer_provider(exporter))
    try:
        with telemetry.tracer().start_as_current_span(telemetry.CALL) as span:
            span.set_attribute("correlation_id", correlation_id)
            span.set_attribute("connection_id", connection_id)
            asyncio.run(coro)
    finally:
        telemetry.tracer_provider().force_flush()
        telemetry.configure()
    return exporter.get_finished_spans()


def attribute_values(spans):
    """Every attribute value on every one of `spans`, stringified -- the alphabet a value-scan
    reads, the same shape `tests/test_zz_b2_leak_scan.py`'s log-record scan already uses."""
    return [str(value) for span in spans for value in span.attributes.values()]

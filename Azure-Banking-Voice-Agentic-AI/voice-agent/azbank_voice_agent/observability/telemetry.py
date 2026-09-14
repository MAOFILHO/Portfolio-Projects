"""The OpenTelemetry seam (issue #61): one TracerProvider/MeterProvider boundary, wired once at
boot, that production and tests attach different things to at the exact same point.

**The seam, precisely.** This module keeps its own process-wide slot for the active pair
(`_STATE`), swapped by `configure()`. It deliberately does **not** use OpenTelemetry's own global
registry (`opentelemetry.trace.set_tracer_provider`) -- that API can be set exactly once per
process and logs a warning on every later call (verified against the pinned SDK release before
relying on either way), which would make per-test isolation impossible in a suite that runs dozens
of telemetry tests in one process (`make test`'s `python -m unittest discover`). This mirrors
`app.py`'s own process-wide-collaborator pattern instead (`_core_banking`, `_call_records`): one
mutable slot, read by `tracer()`/`meter()`, reset to the absent-telemetry default by calling
`configure()` with no arguments.

**D11's corollary, mechanically**: `configure()`'s default (no arguments, or nothing ever called)
is OpenTelemetry's own no-op providers -- zero overhead, and every named constraint (B1, B2, B4)
holds identically, because nothing here is in the call path at all. `tests/test_gate.py`,
`tests/test_zz_b2_leak_scan.py`'s run-wide PIN scan, and `tests/test_whole_call.py`'s B4 cap suite
all run with telemetry never configured, unchanged (`docs/phase6/exit-criteria.md` D11's corollary:
"no named constraint may be enforced by [telemetry]").

**D9's allowlist, mechanically.** `AllowlistSpanProcessor` is the one deny-by-default `SpanProcessor`
D9/D15 describe. It runs first in every `TracerProvider` this module builds, so whatever exporter is
attached after it -- the in-memory one in tests, a real one in production -- only ever sees the
filtered attributes. See its own docstring for why that requires reaching past the SDK's public
`Span.attributes` API rather than using it.
"""
import logging
import os

from opentelemetry import metrics, trace
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import SpanProcessor, TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

log = logging.getLogger("observability")

#: Named for `Resource.create({"service.name": ...})`, below -- what every span and metric this
#: process emits is attributed to.
SERVICE_NAME = "azbank-voice-agent"

# --- D15's table, verbatim -------------------------------------------------------------------
#
# The four span kinds this project's own code creates, and D5's shape: a call contains turns, a
# turn contains tool calls, and a tool call is an attempt whose outcome is the gate's alone. No
# other span name this process might ever produce (FastAPI's and httpx's own auto-instrumentation
# spans included -- see `instrument_fastapi_app`/`instrument_httpx_client` below) appears here,
# and `AllowlistSpanProcessor`'s default for an unrecognised span name is the empty set: deny by
# default means exactly that, for a span kind this table has not named as much as for an
# attribute key it has not named.
CALL = "call"
TURN = "turn"
TOOL_CALL = "tool_call"
CORE_BANKING = "core_banking"

#: `docs/phase6/exit-criteria.md` D15 / issue #61's own table, spelled as code keys. Editing this
#: dict *is* widening B2's new surface -- D9's whole point is that adding a fact means editing the
#: list first, not writing a `set_attribute` call and hoping.
ALLOWLIST: dict[str, frozenset[str]] = {
    CALL: frozenset({
        "correlation_id", "connection_id", "auth_state", "end_reason",
        "turn_count", "duration_ms", "closed_path_taken", "closed_path_cause",
    }),
    TURN: frozenset({"turn_index", "duration_ms", "agent_spoke"}),
    TOOL_CALL: frozenset({"tool_name", "calling_agent", "gate_decision", "outcome_class"}),
    CORE_BANKING: frozenset({"http_method", "route_template", "status_code", "duration_ms"}),
}

#: The tool-call span's `outcome_class` values -- the glossary's four, restated as code (CONTEXT.md
#: already names these; `dispatch/tools.py`'s exception handling is what actually classifies them).
OUTCOME_UNKNOWN_ACCOUNT = "unknown_account"
OUTCOME_DECLINED = "declined"
OUTCOME_UNAVAILABLE = "unavailable"
OUTCOME_MALFORMED = "malformed"

#: D13's two closed-path causes live in `cost/caps.py` (`CLOSED_PATH_BUDGET_SPENT` /
#: `CLOSED_PATH_LEDGER_UNREADABLE`), not here -- that module is where `DailyBudgetSpent.cause` is
#: defined, and this one has no reason to import it just to re-export its own vocabulary back.
#: `closed_path_cause` on the "call" span carries whichever of those two strings `caps.
#: DailyBudgetSpent.cause` held; caller-invisible by construction, since nothing that reads this
#: attribute is on any path a caller's words or the model's replies travel.

class AllowlistSpanProcessor(SpanProcessor):
    """D9 -- the deny-by-default filter every span passes through, no matter which exporter (if
    any) runs after it in the chain.

    **Why this reaches past `ReadableSpan.attributes`.** `Span.end()` marks the span's attribute
    map immutable *before* calling `on_end` on every registered processor (`opentelemetry.sdk.
    trace.Span.end`, pinned SDK release verified 2026-09-13) -- so the public `MutableMapping` API
    (`del span.attributes[key]`) raises `TypeError` here by design, and a filter that only had that
    API could not be a `SpanProcessor` at all; it would have to be a wrapper around every
    `set_attribute` call site instead, which is a different, larger, and less enforceable shape
    than "one deny-by-default `SpanProcessor`" (issue #61's own words). The private backing dict
    (`span._attributes._dict`) has no such guard -- it is a plain `dict`, and `BoundedAttributes`'
    immutability check lives in its `__setitem__`/`__delitem__`, not in bypassing those. Every
    processor registered on one `TracerProvider` receives the *same* `ReadableSpan` object in
    sequence (`SynchronousMultiSpanProcessor.on_end`), so mutating it here -- registered first, by
    `build_tracer_provider` below -- is what a later processor's exporter actually sees.

    This is reaching into two layers of SDK-private state, deliberately rather than by oversight,
    because the SDK offers no public "drop this attribute after the fact" operation. It is pinned
    by this phase's allowlist-exactness test suite, so an `opentelemetry-sdk` upgrade that changes
    this shape is caught by a failing test immediately, not discovered live with a leaked attribute
    already exported.

    Values are never inspected, only keys -- D9's "a scrubber has to be right about every attribute
    every future instrumentation adds; a key allowlist cannot [be silently half-right]."
    """

    def __init__(self, allowlist=None):
        self._allowlist = ALLOWLIST if allowlist is None else allowlist

    def on_start(self, span, parent_context=None):
        pass

    def on_end(self, span):
        allowed = self._allowlist.get(span.name, frozenset())
        attributes = getattr(span, "_attributes", None)
        if not attributes:
            return
        for key in list(attributes):
            if key not in allowed:
                del attributes._dict[key]

    def shutdown(self):
        pass

    def force_flush(self, timeout_millis=30000):
        return True


class _State:
    """The seam's one mutable slot -- see the module docstring for why not OTel's own registry."""

    def __init__(self):
        self.tracer_provider = trace.NoOpTracerProvider()
        self.meter_provider = metrics.NoOpMeterProvider()


_STATE = _State()


def configure(tracer_provider=None, meter_provider=None):
    """The seam itself. `app.py`'s `lifespan()` calls this once, with real providers (or none, if
    nothing is configured yet -- see `configure_from_boot` below). Tests call it with in-memory
    ones, and call it again with no arguments in `tearDown`/`addCleanup` to restore the
    absent-telemetry default -- which is also the default before anything ever calls this at all.
    """
    _STATE.tracer_provider = trace.NoOpTracerProvider() if tracer_provider is None else tracer_provider
    _STATE.meter_provider = metrics.NoOpMeterProvider() if meter_provider is None else meter_provider


def tracer_provider():
    return _STATE.tracer_provider


def meter_provider():
    return _STATE.meter_provider


def tracer():
    """The one tracer every span in this process is created from. Fetched fresh on every call
    (never cached at import time) so that `configure()` swapping the provider mid-run -- which only
    tests ever do -- takes effect on the next span, not the next process."""
    return _STATE.tracer_provider.get_tracer(SERVICE_NAME)


def meter():
    """The one meter every metric instrument in this process is created from. See `tracer()`."""
    return _STATE.meter_provider.get_meter(SERVICE_NAME)


def build_tracer_provider(span_exporter=None):
    """An SDK `TracerProvider` with D9's filter always first, and `span_exporter` (if given) wired
    behind a `BatchSpanProcessor`.

    **Why `BatchSpanProcessor`, always, never `SimpleSpanProcessor`, for a real exporter.** D11's
    fail-open requirement is "never delays a turn" as well as "never raises" -- `BatchSpanProcessor.
    on_end` only appends the span to an in-process queue; the actual `export()` call happens on a
    background thread, and that thread catches every exception the exporter raises
    (`opentelemetry.sdk._shared_internal.BatchProcessor._export`, pinned SDK release verified
    2026-09-13: a bare `except Exception` around the call, logged and swallowed). A hung connection
    ties up that background thread, never the call path -- which is the whole property
    `tests/test_telemetry_fail_open.py` exercises. `SimpleSpanProcessor` calls `export()`
    synchronously on the caller's own thread, which is fail-open for a *raising* exporter (the same
    `except Exception` guard exists there) but not for a *hanging* one, so it is never used here for
    anything but... nothing; this module does not use it at all, on purpose, so production and
    every test that builds a provider through this function exercise the same non-blocking path.
    """
    provider = TracerProvider(resource=Resource.create({"service.name": SERVICE_NAME}))
    provider.add_span_processor(AllowlistSpanProcessor())
    if span_exporter is not None:
        provider.add_span_processor(BatchSpanProcessor(span_exporter))
    return provider


def build_meter_provider(metric_reader=None):
    """An SDK `MeterProvider` reading from `metric_reader` (if given) -- an in-memory reader in
    tests, a real periodic-exporting one in production. No allowlist processor here: D15's table is
    a span-attribute control, and this phase's two metrics (`record_daily_minutes`,
    `record_turn_latency` below) are recorded with no attributes at all, deliberately, so the
    question of a metrics allowlist does not arise in this phase."""
    readers = [] if metric_reader is None else [metric_reader]
    return MeterProvider(resource=Resource.create({"service.name": SERVICE_NAME}), metric_readers=readers)


# --- B4/B5's metrics (D14) ----------------------------------------------------------------------
#
# Names carry the constraint they exist for, the same way this project's log lines already say
# "B4:"/"B5:" inline. Recorded from the same call sites the log lines and the ledger write already
# use -- additive, not a replacement for either (D14: "a proper home instead of being reconstructed
# from spans every time", not instead of the ledger's own fail-closed read).
_DAILY_MINUTES_METRIC = "b4.daily_minutes_used"
_TURN_LATENCY_METRIC = "b5.turn_latency_seconds"


def record_daily_minutes(minutes):
    """B4's daily ledger, as a counter. No attributes: the day key is a date, and a metric carrying
    one would be a per-day cardinality nobody asked for and D15 never listed."""
    meter().create_counter(_DAILY_MINUTES_METRIC, unit="min").add(minutes)


def record_turn_latency(seconds):
    """B5's per-turn round-trip, as a histogram -- the same two log-line anchors already mark
    (`caller turn ended` / `agent audio started`), now with a number attached instead of only an
    order."""
    meter().create_histogram(_TURN_LATENCY_METRIC, unit="s").record(seconds)


def round_duration_ms(seconds):
    """A `duration_ms` attribute value: an **integer** count of milliseconds, not a float count of
    seconds -- not decoration, B2.

    `realtime/session.py`'s own `_record_minutes` already carries this exact reasoning for the
    day's ledger: an unrounded float is seventeen significant digits of essentially meaningless
    binary-floating-point noise, which is exactly the alphabet a four-digit credential gets spelled
    out of by chance (it happened there -- `1.7117999959737062e-06` contains `"9999"`, and the
    run-wide B2 scan went red on a call that had leaked nothing). Rounding to a *few decimal places*
    would still leave that noise in the low digits; converting to a plain integer removes it
    entirely; `round(x)` with no second argument returns one, rather than a float rounded to zero
    decimal places. Every duration this phase puts on a span goes through this one function so the
    reasoning lives in one place rather than four.
    """
    return round(seconds * 1000)


def mark_outcome_class(outcome_class):
    """Set `outcome_class` on whatever "tool call" span is currently open.

    Reached for from deep inside a tool handler (`dispatch/tools.py`'s `_transfer`, for its
    `declined` outcome) rather than threaded down as a parameter: the handler already knows its own
    outcome and the span is already open around it (`dispatch_tool_call` wraps the whole dispatch),
    so this is the same ambient-current-span pattern every other child span in this phase uses to
    avoid changing a collaborator's signature just to carry a span reference one level deeper.
    A no-op if no span is open (e.g. a test that calls a handler directly) -- `trace.get_current_span()`
    returns OpenTelemetry's own non-recording span in that case, whose `set_attribute` is a no-op.
    """
    trace.get_current_span().set_attribute("outcome_class", outcome_class)


# --- FastAPI/httpx instrumentation (issue #61, cleared by docs/phase6/research-content-capture.md)
#
# Both lazily imported: this module is imported by every test in the suite (indirectly, through
# `app.py` and `core_banking/client.py`), and neither instrumentation package needs to be installed
# for a test that never calls either function.


def instrument_fastapi_app(app):
    """Wire the ASGI layer's own spans to this process's `TracerProvider`.

    **Cleared by research, not by assumption**: neither this nor `instrument_httpx_client` below
    captures a request or response body by default or via any documented opt-in flag, at the
    exact pinned release (`docs/phase6/research-content-capture.md` item 16, 2026-09-13). This
    project's one POST route (`/api/incoming-call`) reads `incomingCallContext`/`correlationId`
    only from the JSON body, never a query string, header, or path parameter.

    **One guardrail carried forward, not yet acted on.** The ASGI instrumentation underlying this
    puts the *full* request URL -- query string included -- into the `http.url` span attribute by
    default, redacted only for four cloud-signature parameter names (`AWSAccessKeyId`, `Signature`,
    `sig`, `X-Goog-Signature`) that have nothing to do with this project. `/api/incoming-call` and
    `/api/callbacks` carry no query string today, so there is nothing for that default to leak here
    -- but a future route that puts caller-identifying data in a query string would need
    `excluded_urls=` on this call, or its own redaction, before it ships. Not built now because
    there is no such route to guard yet (issue #61: "don't build machinery for a risk that doesn't
    exist yet").

    Also note: `http.url` (and every other FastAPI/ASGI attribute) is stripped to nothing by
    `AllowlistSpanProcessor` regardless, since the span name FastAPI's instrumentation produces
    (e.g. `"POST /api/incoming-call"`) is not one of D15's four named spans -- deny-by-default
    applies to a span kind this table has not named exactly as it applies to an attribute key it
    has not named. This guardrail is recorded anyway, because a future change to the allowlist
    could reintroduce the risk on purpose without anyone re-deriving it from scratch.
    """
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

    FastAPIInstrumentor.instrument_app(app, tracer_provider=tracer_provider())


def instrument_httpx_client(client):
    """Wire one `httpx.AsyncClient`'s own spans -- the core-banking client's, specifically.

    Per-instance (`HTTPXClientInstrumentor().instrument_client(client, ...)`), not the global
    `instrument()`, which would also wrap `boot.py`'s one-off ARM read and `DefaultAzureCredential`'s
    own token requests -- a bigger surface than issue #61 names, and one this project has no reason
    to widen into without its own decision.
    """
    from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

    HTTPXClientInstrumentor().instrument_client(client, tracer_provider=tracer_provider())


# --- D10's exporter seam: identity vs. connection-string, chosen by config -----------------------
#
# Neither variable below is set by anything this project deploys today -- provisioning Application
# Insights and setting them is issue #62's job, filed and blocked on this one. Until then,
# `span_exporter_from_env`/`metric_reader_from_env` always return None and `configure_from_boot`
# always falls back to the no-op providers `configure()` defaults to. Nothing here is "wired to a
# real Azure resource" in the sense the hard limits on this ticket mean: the resource does not
# exist, and no environment this project's own config touches ever sets these.

#: Azure Monitor's own documented variable name for the ingestion endpoint.
APPLICATIONINSIGHTS_CONNECTION_STRING_VAR = "APPLICATIONINSIGHTS_CONNECTION_STRING"

#: "identity" (D10's preferred path, consistent with Phase 7's no-keys direction) or
#: "connection_string" (the named fallback, carrying a Phase 7 debt if it is ever the one actually
#: used). Anything else, or the variable's absence, means identity.
AZURE_MONITOR_AUTH_VAR = "AZURE_MONITOR_AUTH"
_CONNECTION_STRING_AUTH = "connection_string"

#: A short, non-blocking budget on the exporter's own network calls. `BatchSpanProcessor` already
#: keeps a hung exporter off the call path (see `build_tracer_provider`'s docstring), but nothing
#: stops it from tying up its background thread indefinitely against an exporter with no timeout of
#: its own -- this is that timeout, not a second copy of B4's caps.
EXPORTER_TIMEOUT_SECONDS = 5.0


def span_exporter_from_env(env=None):
    """The real span exporter, or `None` if nothing is configured -- which is every environment
    this project runs in today.

    Lazily imports `azure-monitor-opentelemetry-exporter` the way `call_records/store.py` lazily
    imports `azure-data-tables`: declared as a real dependency because this function imports it
    directly, but nothing breaks if it is never installed and this function is never called (which
    is the case until issue #62 sets `APPLICATIONINSIGHTS_CONNECTION_STRING`).
    """
    env = os.environ if env is None else env
    connection_string = env.get(APPLICATIONINSIGHTS_CONNECTION_STRING_VAR)
    if not connection_string:
        return None
    from azure.monitor.opentelemetry.exporter import AzureMonitorTraceExporter

    kwargs = {"connection_string": connection_string, "timeout": EXPORTER_TIMEOUT_SECONDS}
    if env.get(AZURE_MONITOR_AUTH_VAR) != _CONNECTION_STRING_AUTH:
        from azure.identity import DefaultAzureCredential

        kwargs["credential"] = DefaultAzureCredential()
    return AzureMonitorTraceExporter(**kwargs)


def metric_reader_from_env(env=None):
    """The real metric reader, or `None`. See `span_exporter_from_env` -- same variables, same
    lazy-import discipline, same "never called until issue #62" standing."""
    env = os.environ if env is None else env
    connection_string = env.get(APPLICATIONINSIGHTS_CONNECTION_STRING_VAR)
    if not connection_string:
        return None
    from azure.monitor.opentelemetry.exporter import AzureMonitorMetricExporter
    from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader

    kwargs = {"connection_string": connection_string, "timeout": EXPORTER_TIMEOUT_SECONDS}
    if env.get(AZURE_MONITOR_AUTH_VAR) != _CONNECTION_STRING_AUTH:
        from azure.identity import DefaultAzureCredential

        kwargs["credential"] = DefaultAzureCredential()
    return PeriodicExportingMetricReader(AzureMonitorMetricExporter(**kwargs))


def configure_from_boot(env=None):
    """Called once, from `app.py`'s `lifespan()` -- telemetry's equivalent of `boot.
    assert_boot_safety()`, except it never refuses to start.

    **Never raises, unlike the B3 guard it sits beside.** D11 says telemetry fails open; a boot that
    crashed because an exporter could not be built would be telemetry taking down a call path it is
    supposed to be evidence for, which is the one thing this phase must never do. Any failure here
    is logged loudly and answered by falling back to the no-op providers `configure()` defaults to
    -- the same standing as an unreachable exporter discovered later, not a separate case.
    """
    try:
        configure(
            build_tracer_provider(span_exporter_from_env(env)),
            build_meter_provider(metric_reader_from_env(env)),
        )
    except Exception:
        log.exception("telemetry did not configure at boot; continuing with telemetry absent (D11)")
        configure()

"""ADOT-to-X-Ray application tracing -- `ADR-018`, Phase 14. Hand-placed spans, no AWS auto-instrumentation
exec wrapper (Marco's decision: `AWS_LAMBDA_EXEC_WRAPPER` is never set -- see `infra/terraform/stacks/main/
lambda.tf`; the latency headroom against constraint 14's 1,800ms p95 budget was measured too thin for the
wrapper's added per-invocation overhead). This module builds its own `TracerProvider` and exports OTLP-HTTP
to `localhost:4318`, where the ADOT Lambda layer's bundled collector extension picks it up and forwards to
X-Ray via `PutTraceSegments` -- the layer supplies the sink, this module supplies the spans.

**Three hard constraints this module exists to satisfy, in order of how badly violating each one would
hurt:**

1. **Import-safe when `opentelemetry` is absent.** It ships on the ADOT layer at `/opt/python` in real
   Lambda, not in `fnol-codehook-deps` and not in `pyproject.toml`'s runtime `dependencies` -- every local
   run, test, eval, and simulator invocation has no such layer and must keep working completely unchanged.
   The single module-level import below is wrapped in `try/except ImportError`; every span-creating helper
   in this module degrades to a transparent no-op when `_otel_trace is None`.
2. **No AWS client (boto3/botocore) touched at import time or via this module's setup path** -- the same
   SnapStart-compatible posture `api/lex_codehook.py` already holds for the rest of the codehook. All real
   OTel imports happen lazily inside `_install()`, called on first use and cached in `_PROVIDER`, mirroring
   `lex_codehook.py`'s own `_GRAPH`/`_get_graph()` pattern exactly. The exporter is the OTLP **HTTP**
   exporter (`opentelemetry.exporter.otlp.proto.http.trace_exporter.OTLPSpanExporter`, backed by
   `requests`), never a SigV4-signing exporter -- that would pull in boto3, which this module must never do.
3. **Flushes before the handler returns.** `BatchSpanProcessor` exports on a background thread, and Lambda
   freezes the execution environment the instant the handler returns -- an unflushed batch can vanish
   mid-export with no error anywhere. `flush()` below is what `handler()` (`api/lex_codehook.py`) calls in a
   `finally` block wrapping its whole body, with a short hard timeout (`ADR-018`'s own latency-headroom
   concern) so a stuck collector extension can never blow the per-turn budget, and a log line on timeout so
   a silent trace gap is visible in CloudWatch rather than silently assumed complete.

**Span attributes carry IDs and metrics ONLY, per `ADR-018` -- never utterance text, response text, or slot
values.** `_ALLOWED_SPAN_ATTRIBUTES` below enumerates every key this module will ever set. Every
attribute-setting helper checks a key against it before calling `span.set_attribute` and **drops (logs a
warning, does not raise) an unlisted key** rather than setting it -- chosen over raising because this is a
live-call observability add-on on a 1,800ms voice-turn budget, and a bug in a NEW attribute someone adds
should never be able to take down an in-progress call the way an unhandled exception here would; the drop is
loud (a CloudWatch line), not silent. A key added deliberately is a one-line addition to the frozenset below;
a key added by accident (a future edit that widens what a decorator captures without thinking about `ADR-011`
first) is caught by this check and by `tests/unit/test_tracing.py`'s own PII-scan of every span attribute
value, not shipped.

**Root span kind is `INTERNAL`, not `SERVER` -- read this before "fixing" it.** The X-Ray OTLP exporter's
own rule is that a span whose parent is not `SERVER`/`CONSUMER` becomes an X-Ray *subsegment* of whatever
segment the parent context names. `start_turn_span` extracts its parent context from the `_X_AMZN_TRACE_ID`
environment variable Lambda sets when `tracing_config.mode = "Active"` (`AwsXRayLambdaPropagator` reads that
var directly -- Lex never sends a trace header, so this is the only parent-linking mechanism available here)
-- that parent is the `AWS::Lambda::Function` segment Lambda's own instrumentation already opened. Marking
`fnol.turn` `INTERNAL` is what nests it as a subsegment of that function segment, in the SAME trace; marking
it `SERVER` would make the X-Ray exporter treat it as the root of a second, disconnected trace instead. Every
child span in this module (`traced_span`) is also `INTERNAL`, for the identical reason one level down.
"""

from __future__ import annotations

import inspect
import logging
import os
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from functools import wraps
from typing import Any, ParamSpec, TypeVar

try:
    from opentelemetry import trace as _otel_trace
except (
    ImportError
):  # pragma: no cover - exercised by test_tracing.py (subprocess / sys.modules patch)
    _otel_trace = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

P = ParamSpec("P")
R = TypeVar("R")

# ADR-018: "span attributes are contactId, node name, model ID, latency, token counts, guardrail action.
# No span attribute ever carries caller utterance text, generated response text, or slot values." This is
# that boundary made mechanical rather than a docstring promise -- see the module docstring's "drop, don't
# raise" reasoning above for why an unlisted key is logged and dropped, not an exception.
_ALLOWED_SPAN_ATTRIBUTES: frozenset[str] = frozenset(
    {
        # fnol.turn -- the root span (handler()'s whole body).
        "fnol.contact_id",
        "fnol.dispatch_path",
        "fnol.turn_input_len",
        # fnol.node.<name> -- one per LangGraph node (agents/graph.py's _add_traced_node).
        "fnol.node.name",
        # bedrock.converse.classify_turn / bedrock.converse.generate_response (aws/bedrock_router.py).
        "bedrock.model_id",
        "bedrock.input_tokens",
        "bedrock.output_tokens",
        "bedrock.stop_reason",
        # bedrock.apply_guardrail (guardrails/client.py). `usage_json` mirrors observability/
        # guardrail_metrics.py::emit_guardrail_usage's own `json.dumps(dict(usage), sort_keys=True)` shape
        # exactly, rather than enumerating each of Bedrock's five-to-seven usage-unit key names a second
        # place here -- the same "one source of truth" reasoning aws/bedrock_router.py's own
        # build_classify_turn_tool_spec() docstring gives for deriving a schema instead of retyping it.
        "fnol.guardrail.source",
        "fnol.guardrail.action",
        "fnol.guardrail.blocked",
        "fnol.guardrail.masked",
        "fnol.guardrail.usage_json",
        # mcp.<tool_name> -- one per MCP domain-function definition (mcp/{policy,claims,contact,
        # escalation}_server.py).
        "fnol.mcp.tool_name",
        "fnol.mcp.server_domain",
        "fnol.mcp.found",
        "fnol.mcp.contact_id",
    }
)

_PROVIDER: Any = (
    None  # lazily built and cached per warm instance -- mirrors lex_codehook.py's `_GRAPH`.
)
_INSTALL_FAILED = (
    False  # sticky: once _install() has thrown once, stop retrying every call this instance.
)
_ACTIVE_TOKENS: dict[int, Any] = (
    {}
)  # id(span) -> context.attach() token, for start_turn_span/end_turn_span.

# Matches `flush()`'s own default `timeout_millis` (200) -- see `_install()`'s comment on why the
# EXPORTER's own timeout, not `force_flush`'s argument, is what actually bounds a stuck-collector call.
_EXPORT_TIMEOUT_SECONDS = 0.2


def _install() -> Any:
    """Builds and returns ONE `TracerProvider`, real `opentelemetry` imports all local to this function --
    never at module load (constraint 2 above). Called at most once per warm Lambda instance, from
    `_get_tracer_provider()`, and cached in `_PROVIDER`.
    """
    from opentelemetry import trace
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.propagate import set_global_textmap
    from opentelemetry.propagators.aws import AwsXRayLambdaPropagator
    from opentelemetry.sdk.extension.aws.trace import AwsXRayIdGenerator
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.sdk.trace.sampling import ALWAYS_ON, ParentBased

    provider = TracerProvider(
        id_generator=AwsXRayIdGenerator(),
        # ADR-018's demo-scale cost table already assumes every turn is recorded (100k free traces/mo
        # against ~100 calls/mo) -- ParentBased(root=ALWAYS_ON) samples every root span, deferring to the
        # parent's own sampling decision when one exists (there never is one here; see the module
        # docstring's INTERNAL-vs-SERVER note).
        sampler=ParentBased(root=ALWAYS_ON),
        resource=Resource.create(
            {
                "service.name": os.environ.get("AWS_LAMBDA_FUNCTION_NAME", "fnol-codehook"),
                "cloud.platform": "aws_lambda",
                "cloud.region": os.environ.get("AWS_REGION", ""),
            }
        ),
    )
    # `timeout=_EXPORT_TIMEOUT_SECONDS`, not the exporter's own 10s default -- found empirically while
    # building this module, not assumed: `BatchSpanProcessor.force_flush(timeout_millis=...)` does NOT
    # preempt an in-progress `OTLPSpanExporter.export()` call already under way -- that call's OWN
    # `self._timeout` (10s unless overridden here) sets the deadline its internal retry-with-backoff loop
    # runs against, and `force_flush`'s `timeout_millis` argument does not touch it. Against an
    # unreachable collector this measured ~7s wall-clock through the exporter's default retry backoff, on
    # a $0.20s-budget flush call -- exactly the "stuck collector blows the turn budget" failure this
    # module exists to prevent. Setting the exporter's own timeout short is what actually bounds it: on
    # the first failed attempt, `_MAX_RETRYS`' backoff (~0.8-1.2s) exceeds the remaining deadline
    # immediately, so `export()` returns FAILURE without sleeping through a backoff at all (measured
    # ~0.16s wall-clock end to end with this fix, same unreachable-endpoint scenario).
    provider.add_span_processor(
        BatchSpanProcessor(
            OTLPSpanExporter(
                endpoint="http://localhost:4318/v1/traces",
                timeout=_EXPORT_TIMEOUT_SECONDS,
            )
        )
    )
    trace.set_tracer_provider(provider)
    # Reads `_X_AMZN_TRACE_ID` -- see the module docstring's INTERNAL-vs-SERVER note on why this is what
    # makes fnol.turn nest under the AWS::Lambda::Function segment instead of starting a disconnected
    # second trace.
    set_global_textmap(AwsXRayLambdaPropagator())
    return provider


def _get_tracer_provider() -> Any:
    """Returns the cached `TracerProvider`, building it on first call. Returns `None` (never raises) when
    `opentelemetry` is absent, or when `_install()` itself failed -- a broken tracing setup must never take
    an otherwise-healthy turn down with it, so every caller in this module already tolerates a `None`
    provider/span/tracer at each step.
    """
    global _PROVIDER, _INSTALL_FAILED
    if _otel_trace is None or _INSTALL_FAILED:
        return None
    if _PROVIDER is None:
        try:
            _PROVIDER = _install()
        except Exception:  # noqa: BLE001 - tracing must never be why a turn fails
            logger.warning(
                "tracing: failed to initialize the OTel TracerProvider -- tracing disabled for the "
                "remainder of this execution environment",
                exc_info=True,
            )
            _INSTALL_FAILED = True
            return None
    return _PROVIDER


def set_span_attribute(span: Any, key: str, value: Any) -> None:
    """Sets one attribute on `span`, after checking `key` against `_ALLOWED_SPAN_ATTRIBUTES`. No-ops
    (never raises) when `span` is `None` (the no-otel/no-op case every caller in this module produces) or
    when `key` is not on the allowlist -- see the module docstring for why an unlisted key is dropped with
    a log line rather than raising.
    """
    if _otel_trace is None or span is None:
        return
    if key not in _ALLOWED_SPAN_ATTRIBUTES:
        logger.warning(
            "tracing: dropped span attribute %r -- not a member of _ALLOWED_SPAN_ATTRIBUTES "
            "(ADR-018 IDs-and-metrics-only boundary)",
            key,
        )
        return
    try:
        span.set_attribute(key, value)
    except Exception:  # noqa: BLE001 - a bad attribute value must not fail the turn it's describing
        logger.warning("tracing: failed to set span attribute %r", key, exc_info=True)


def annotate_current_span(attributes: Mapping[str, Any]) -> None:
    """Sets every `(key, value)` in `attributes` on whatever span is currently active (`traced`'s wrapper,
    typically), via `set_span_attribute`'s own allowlist check. The mechanism `aws/bedrock_router.py` and
    `guardrails/client.py` use to attach result-dependent attributes (model id, token counts, guardrail
    action...) that only exist AFTER the wrapped function's own body has done its work -- a decorator
    wrapping the whole function can never see them, since it only ever has the function's final return
    value, which for `classify_turn` is a `TurnClassification` that has already discarded the raw
    Converse response's `usage`/`stopReason` fields. No-op when `opentelemetry` is absent.
    """
    if _otel_trace is None:
        return
    span = _otel_trace.get_current_span()
    for key, value in attributes.items():
        set_span_attribute(span, key, value)


@contextmanager
def traced_span(name: str) -> Iterator[Any]:
    """A child span named `name`, `SpanKind.INTERNAL`, active only for the duration of the `with` block --
    the one reusable primitive every other helper in this module builds on (`traced`, `traced_mcp_tool`,
    and `agents/graph.py`'s own node wrapper all use this directly). Yields `None`, does nothing, when
    `opentelemetry` is absent or no provider is available -- every caller here already tolerates that.

    Uses `start_as_current_span`, not a bare `start_span`, specifically so nested spans opened deeper in
    the call stack (a node span containing a bedrock/mcp span, say) pick up this span as their parent via
    normal `contextvars` propagation -- the whole call tree from `handler()` down is synchronous, single-
    threaded Python, so no explicit parent-passing is needed anywhere below the root span.
    """
    provider = _get_tracer_provider()
    if provider is None:
        yield None
        return
    tracer = provider.get_tracer(__name__)
    with tracer.start_as_current_span(name, kind=_otel_trace.SpanKind.INTERNAL) as span:
        yield span


def traced(name: str) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Decorator: wraps `fn` in a `traced_span(name)` for the duration of the call. Returns `fn`
    UNCHANGED (not a wrapper that no-ops at call time) when `opentelemetry` is absent, so the no-otel path
    has zero added call overhead, not just zero added behavior.

    Used on `aws/bedrock_router.py`'s two Converse call paths and `guardrails/client.py`'s
    `apply_guardrail` -- each of those functions calls `annotate_current_span` itself, once it has the
    result-dependent values this decorator alone cannot see (see that function's own docstring).
    """

    def decorator(fn: Callable[P, R]) -> Callable[P, R]:
        if _otel_trace is None:
            return fn

        @wraps(fn)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            with traced_span(name):
                return fn(*args, **kwargs)

        return wrapper

    return decorator


def traced_mcp_tool(
    tool_name: str,
    server_domain: str,
    *,
    contact_id_arg: str | None = None,
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Decorator for one MCP domain-function definition (`mcp/{policy,claims,contact,escalation}_
    server.py`) -- applied at the definition, per ADR-018's own instruction, so it covers every caller
    (the in-process adapter AND the MCP-wire-protocol adapter, `ADR-012`'s two-adapters-one-handler shape)
    without touching either call site. Span name is `mcp.<tool_name>`.

    Sets `fnol.mcp.tool_name`/`fnol.mcp.server_domain` unconditionally; `fnol.mcp.contact_id` only when
    `contact_id_arg` names a real parameter of `fn` and the call actually supplies it (only
    `initiate_escalation`'s `contact_id` qualifies among the six decorated functions today -- the others
    take policy/claim numbers, not a contact id). `fnol.mcp.found` is set `True` once `fn` returns without
    raising -- every one of these six handlers raises a domain-specific `*NotFoundError`/`*Error` rather
    than returning `None`/`False` on a miss (see each module's own exception classes), so "returned at
    all" already IS the cheap found/success signal this attribute exists for; a raised exception leaves it
    unset, which is the honest value (the span itself still records the exception via OTel's own default
    exception recording on `__exit__`).

    Returns `fn` unchanged when `opentelemetry` is absent.
    """

    def decorator(fn: Callable[P, R]) -> Callable[P, R]:
        if _otel_trace is None:
            return fn
        sig = inspect.signature(fn) if contact_id_arg is not None else None

        @wraps(fn)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            with traced_span(f"mcp.{tool_name}") as span:
                set_span_attribute(span, "fnol.mcp.tool_name", tool_name)
                set_span_attribute(span, "fnol.mcp.server_domain", server_domain)
                if sig is not None and contact_id_arg is not None:
                    try:
                        bound = sig.bind_partial(*args, **kwargs)
                    except TypeError:
                        bound = None
                    contact_id = bound.arguments.get(contact_id_arg) if bound is not None else None
                    if contact_id is not None:
                        set_span_attribute(span, "fnol.mcp.contact_id", str(contact_id))
                result = fn(*args, **kwargs)
                set_span_attribute(span, "fnol.mcp.found", True)
                return result

        return wrapper

    return decorator


def start_turn_span(*, contact_id: str, turn_input_len: int) -> Any:
    """Starts the root `fnol.turn` span and attaches it as the current OTel context (so every span opened
    deeper in this turn's call tree nests under it via ordinary `contextvars` propagation -- see
    `traced_span`'s own docstring). Returns the span (or `None` under no-otel/no-provider), which the
    caller (`api/lex_codehook.py::handler`) must pass to `end_turn_span` in a `finally` block, followed by
    `flush()`.

    Deliberately two separate functions (`start_turn_span`/`end_turn_span`), not one context manager --
    `handler()` needs to set `fnol.dispatch_path` from several different return points inside its own
    try/except, and needs `flush()` to run strictly AFTER the span has ended (a span not yet ended is not
    yet queued for export by `BatchSpanProcessor`, so flushing before `end_turn_span` would export nothing
    for this turn) -- both are easier to state correctly as an explicit start/end pair than to thread
    through a single `with` block that would have to enclose the flush call inside itself to get the
    ordering backwards.
    """
    if _otel_trace is None:
        return None
    provider = _get_tracer_provider()
    if provider is None:
        return None

    from opentelemetry import context as otel_context
    from opentelemetry.propagators.aws import AwsXRayLambdaPropagator

    # Lex never sends a trace header; `_X_AMZN_TRACE_ID` (env var) is the only parent-linking mechanism
    # available here -- see the module docstring's INTERNAL-vs-SERVER note.
    parent_ctx = AwsXRayLambdaPropagator().extract({})
    tracer = provider.get_tracer(__name__)
    span = tracer.start_span("fnol.turn", context=parent_ctx, kind=_otel_trace.SpanKind.INTERNAL)
    token = otel_context.attach(_otel_trace.set_span_in_context(span, parent_ctx))
    _ACTIVE_TOKENS[id(span)] = token

    set_span_attribute(span, "fnol.contact_id", contact_id)
    set_span_attribute(span, "fnol.turn_input_len", turn_input_len)
    return span


def end_turn_span(span: Any) -> None:
    """Ends `span` and detaches the context token `start_turn_span` attached. No-op on `None`
    (opentelemetry absent, or `start_turn_span` itself returned `None`)."""
    if _otel_trace is None or span is None:
        return
    token = _ACTIVE_TOKENS.pop(id(span), None)
    try:
        span.end()
    finally:
        if token is not None:
            from opentelemetry import context as otel_context

            otel_context.detach(token)


def flush(timeout_millis: int = 200) -> None:
    """Force-exports whatever `BatchSpanProcessor` has queued (i.e. every span already `end()`-ed by the
    time this is called). Short hard timeout, per the module docstring's constraint 3 -- a stuck collector
    extension must never blow the per-turn latency budget. Logs a warning (never raises) on a timeout or
    an export failure, so a silent trace gap is visible in CloudWatch rather than silently assumed
    complete. No-op when no provider was ever built (opentelemetry absent, or `_install()` failed) --
    nothing to flush.
    """
    if _PROVIDER is None:
        return
    try:
        flushed = _PROVIDER.force_flush(timeout_millis=timeout_millis)
        if not flushed:
            logger.warning(
                "tracing: force_flush did not complete within %dms -- some spans for this turn may not "
                "have been exported",
                timeout_millis,
            )
    except Exception:  # noqa: BLE001 - flushing traces must never fail the turn it's describing
        logger.warning("tracing: force_flush raised", exc_info=True)


__all__ = [
    "annotate_current_span",
    "end_turn_span",
    "flush",
    "set_span_attribute",
    "start_turn_span",
    "traced",
    "traced_mcp_tool",
    "traced_span",
]

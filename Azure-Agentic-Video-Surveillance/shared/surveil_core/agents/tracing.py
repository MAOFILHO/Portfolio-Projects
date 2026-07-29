"""Optional LLM-level tracing export to Langfuse via OpenTelemetry (OTLP).

Layered on top of whatever tracer provider is already active (Application
Insights' `configure_azure_monitor()` in the backend, or a fresh one here if
nothing configured it yet, e.g. in the Function or the local diagnose_webrtc.py
CLI) -- every span still reaches Azure Monitor too; nothing about the existing
observability wiring changes. Disabled (no-op) unless LANGFUSE_PUBLIC_KEY and
LANGFUSE_SECRET_KEY are both set.

Semantic Kernel's own OTel instrumentation (chat completion + tool-call spans)
is gated behind two of its own env vars: SEMANTICKERNEL_EXPERIMENTAL_GENAI_ENABLE_OTEL_DIAGNOSTICS
and its "_SENSITIVE" counterpart (the one that includes actual prompt/
completion text in span attributes -- enabled deliberately, since the whole
point of wiring this up is full agent traceability; be aware this means
prompt/completion content leaves the process to Langfuse's cloud, per
LANGFUSE_HOST).

These two env vars are set as a MODULE-LEVEL side effect below (not inside a
function) and this module is imported first in `agents/__init__.py`, before
anything else in this package. This is load-bearing, not stylistic: Semantic
Kernel reads them exactly once into a module-level singleton
(`MODEL_DIAGNOSTICS_SETTINGS = ModelDiagnosticSettings()` in
`semantic_kernel/utils/telemetry/model_diagnostics/decorators.py`) at IMPORT
TIME of that module -- setting the env var later, e.g. inside
`configure_langfuse_tracing()` as this file previously did, has no effect,
because by the time any of our own functions run, `semantic_kernel` has
already been imported (transitively, by `kernel_factory.py`/
`diagnostic_agent.py` et al., themselves imported at the Function's/backend's
cold start) and that settings singleton is already frozen at its default
(`False`). Confirmed live: our own OTLP exporter/auth was verified working
end-to-end with a manual test span, yet zero spans ever appeared for real
Triage/Notification Policy agent chat-completion calls in production until
this ordering was fixed -- see docs/troubleshooting.md #20.
"""

from __future__ import annotations

import base64
import json
import logging
import os
from contextlib import contextmanager

logger = logging.getLogger("surveil_core.agents.tracing")

if os.environ.get("LANGFUSE_PUBLIC_KEY") and os.environ.get("LANGFUSE_SECRET_KEY"):
    os.environ.setdefault("SEMANTICKERNEL_EXPERIMENTAL_GENAI_ENABLE_OTEL_DIAGNOSTICS", "true")
    os.environ.setdefault("SEMANTICKERNEL_EXPERIMENTAL_GENAI_ENABLE_OTEL_DIAGNOSTICS_SENSITIVE", "true")

_configured = False
# Set only when this call actually attached a Langfuse span processor to a
# provider -- distinct from `_configured`, which is also true on the early
# no-op return (keys unset). `flush_langfuse_tracing()` must be a safe no-op
# in that case, since there is nothing to flush and the active provider may
# not even support `force_flush` (e.g. the SDK's default no-op provider).
_provider_with_langfuse_processor = None


def configure_langfuse_tracing() -> None:
    global _configured, _provider_with_langfuse_processor
    if _configured:
        return
    _configured = True

    public_key = os.environ.get("LANGFUSE_PUBLIC_KEY")
    secret_key = os.environ.get("LANGFUSE_SECRET_KEY")
    if not public_key or not secret_key:
        return

    host = os.environ.get("LANGFUSE_HOST", "https://cloud.langfuse.com")
    auth = base64.b64encode(f"{public_key}:{secret_key}".encode()).decode()

    from opentelemetry import trace
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    exporter = OTLPSpanExporter(
        endpoint=f"{host}/api/public/otel/v1/traces",
        # x-langfuse-ingestion-version=4: without this, Langfuse documents up
        # to a 10-minute delay before OTLP-ingested spans appear on the v4
        # data model (and the v2 Observations API this project's own
        # diagnostics/audits query) -- confirmed the hard way chasing an
        # empty observations-list response for a trace that was already
        # visible via the legacy v3 traces endpoint.
        headers={"Authorization": f"Basic {auth}", "x-langfuse-ingestion-version": "4"},
    )
    processor = BatchSpanProcessor(exporter)

    provider = trace.get_tracer_provider()
    if not isinstance(provider, TracerProvider):
        # No real SDK provider configured yet (Application Insights wasn't
        # set up in this process, or this is the local diagnose_webrtc.py
        # CLI) -- create one so Langfuse still gets spans either way. Both
        # resource attributes below only apply on THIS branch -- a Resource
        # can't be amended after a TracerProvider already exists, so when
        # Application Insights created the provider first (the backend), its
        # spans keep Azure Monitor's default service name/no environment tag
        # instead (see docs/troubleshooting.md #20).
        #
        # service.name: this project's Langfuse traces share one
        # project/API-key pair with every other unrelated codebase reusing
        # the same Langfuse account (see docs/troubleshooting.md #20), so a
        # specific, non-generic name is the only thing that lets you filter
        # for just this system's spans inside a shared project.
        #
        # langfuse.environment: one of the three OTel resource attributes
        # Langfuse recognizes for its "environment" facet (the others are
        # deployment.environment.name / deployment.environment) -- keeps a
        # local/manual diagnose_webrtc.py run from polluting production
        # dashboards. Defaults to "production" since the Function is this
        # attribute's primary caller; override via LANGFUSE_TRACING_ENVIRONMENT
        # (matches the env var name Langfuse's own SDK reads).
        service_name = os.environ.get("OTEL_SERVICE_NAME", "azure-agentic-video-surveillance")
        environment = os.environ.get("LANGFUSE_TRACING_ENVIRONMENT", "production")
        provider = TracerProvider(
            resource=Resource.create({"service.name": service_name, "langfuse.environment": environment})
        )
        trace.set_tracer_provider(provider)
    provider.add_span_processor(processor)
    _provider_with_langfuse_processor = provider
    logger.info("Langfuse tracing configured (host=%s)", host)


def flush_langfuse_tracing(timeout_millis: int = 5000) -> None:
    """Force-export any spans still buffered in the Langfuse span processor.

    Required for short-lived processes -- an Azure Function invocation can
    complete and the worker process can be reused or torn down well before
    BatchSpanProcessor's own periodic export timer would have fired,
    silently dropping that invocation's spans. Call this once, at the very
    end of each invocation (a `finally` block), not just once at cold start.
    No-ops if Langfuse tracing was never configured (keys unset).
    """
    global _provider_with_langfuse_processor
    if _provider_with_langfuse_processor is None:
        return
    _provider_with_langfuse_processor.force_flush(timeout_millis=timeout_millis)


@contextmanager
def agent_span(name: str, *, input: dict, metadata: dict | None = None, tags: list[str] | None = None):
    """Wrap one agent decision in an explicit, business-meaningful OTel span.

    Without this, a Langfuse trace for e.g. the Triage Agent is just Semantic
    Kernel's own raw "chat.completions <deployment>" leaf span -- real token
    usage and latency, but no way to tell which agent ran, for which camera
    or frame, or what it actually decided (confirmed live: input/output on
    that raw span are empty, since SK emits prompt/completion as span
    *events*, which Langfuse's OTel mapping doesn't read for input/output --
    see docs/troubleshooting.md #20). This gives every agent call its own
    parent span with `langfuse.observation.type=agent` (so it shows up as
    its own node in Langfuse's Agent Graph, per Langfuse's own multi-agent
    instrumentation guidance) and a deliberately curated input/output --
    the actual business decision (detection tags in, escalate/channels
    decision out), not the raw LLM prompt/completion, matching Langfuse's
    own guidance to keep trace input/output meaningful rather than a raw
    dump of function arguments. Semantic Kernel's own chat-completion span
    nests underneath this automatically via normal OTel span-context
    propagation -- no extra wiring needed for that part.

    Safe to use unconditionally, Langfuse configured or not -- with no SDK
    tracer provider active, this is a harmless no-op OTel span nobody
    exports; the caller's own logic never has to check `_configured`.
    """
    from opentelemetry import trace

    tracer = trace.get_tracer("surveil_core.agents")
    with tracer.start_as_current_span(name) as span:
        span.set_attribute("langfuse.observation.type", "agent")
        span.set_attribute("langfuse.observation.input", json.dumps(input, default=str))
        if metadata:
            for key, value in metadata.items():
                span.set_attribute(f"langfuse.observation.metadata.{key}", str(value))
        if tags:
            span.set_attribute("langfuse.trace.tags", tags)
        yield span


def set_agent_output(span, output: dict) -> None:
    """Set the curated business-level output on a span opened via `agent_span`."""
    span.set_attribute("langfuse.observation.output", json.dumps(output, default=str))

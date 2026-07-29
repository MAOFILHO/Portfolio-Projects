"""Optional LLM-level tracing export to Langfuse via OpenTelemetry (OTLP).

Layered on top of whatever tracer provider is already active (Application
Insights' `configure_azure_monitor()` in the backend, or a fresh one here if
nothing configured it yet, e.g. in the Function or the local diagnose_webrtc.py
CLI) -- every span still reaches Azure Monitor too; nothing about the existing
observability wiring changes. Disabled (no-op) unless LANGFUSE_PUBLIC_KEY and
LANGFUSE_SECRET_KEY are both set.

Semantic Kernel's own OTel instrumentation (chat completion + tool-call spans)
is gated behind two of its own env vars, both enabled here whenever Langfuse
tracing is turned on: SEMANTICKERNEL_EXPERIMENTAL_GENAI_ENABLE_OTEL_DIAGNOSTICS
and its "_SENSITIVE" counterpart (the one that includes actual prompt/
completion text in span attributes -- enabled deliberately, since the whole
point of wiring this up is full agent traceability; be aware this means
prompt/completion content leaves the process to Langfuse's cloud, per
LANGFUSE_HOST).
"""

from __future__ import annotations

import base64
import logging
import os

logger = logging.getLogger("surveil_core.agents.tracing")

_configured = False


def configure_langfuse_tracing() -> None:
    global _configured
    if _configured:
        return
    _configured = True

    public_key = os.environ.get("LANGFUSE_PUBLIC_KEY")
    secret_key = os.environ.get("LANGFUSE_SECRET_KEY")
    if not public_key or not secret_key:
        return

    # Semantic Kernel checks these once, when a settings object is first
    # constructed inside its telemetry code -- must be set before any kernel
    # function/chat-completion call happens, which build_kernel() -- the sole
    # caller of this function -- guarantees.
    os.environ.setdefault("SEMANTICKERNEL_EXPERIMENTAL_GENAI_ENABLE_OTEL_DIAGNOSTICS", "true")
    os.environ.setdefault("SEMANTICKERNEL_EXPERIMENTAL_GENAI_ENABLE_OTEL_DIAGNOSTICS_SENSITIVE", "true")

    host = os.environ.get("LANGFUSE_HOST", "https://cloud.langfuse.com")
    auth = base64.b64encode(f"{public_key}:{secret_key}".encode()).decode()

    from opentelemetry import trace
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    exporter = OTLPSpanExporter(
        endpoint=f"{host}/api/public/otel/v1/traces",
        headers={"Authorization": f"Basic {auth}"},
    )
    processor = BatchSpanProcessor(exporter)

    provider = trace.get_tracer_provider()
    if not isinstance(provider, TracerProvider):
        # No real SDK provider configured yet (Application Insights wasn't
        # set up in this process, or this is the local diagnose_webrtc.py
        # CLI) -- create one so Langfuse still gets spans either way.
        # A specific, non-generic name matters here: this project's Langfuse
        # traces share one project/API-key pair with every other unrelated
        # codebase reusing the same Langfuse account (see docs/troubleshooting.md
        # "Langfuse traces show up mixed with other projects"), so this is the
        # only thing that lets you filter/search for just this system's spans
        # inside that shared project.
        service_name = os.environ.get("OTEL_SERVICE_NAME", "azure-realtime-video-surveillance")
        provider = TracerProvider(resource=Resource.create({"service.name": service_name}))
        trace.set_tracer_provider(provider)
    provider.add_span_processor(processor)
    logger.info("Langfuse tracing configured (host=%s)", host)

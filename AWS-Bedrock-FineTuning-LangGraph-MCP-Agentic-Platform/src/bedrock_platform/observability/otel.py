from fastapi import FastAPI
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from bedrock_platform.config.settings import Settings
from bedrock_platform.observability.console_spans import TerseConsoleSpanExporter


def setup_observability(app: FastAPI, settings: Settings) -> None:
    """Wires tracing before any request-handling logic runs. Always emits to the
    terminal via the console exporter; adds the OTLP/CloudWatch exporter only if
    OTEL_EXPORTER_OTLP_ENDPOINT is configured. Never crashes on a missing endpoint —
    tracing degrades to console-only rather than blocking startup."""
    provider = TracerProvider(resource=Resource.create({SERVICE_NAME: "bedrock-platform"}))
    provider.add_span_processor(BatchSpanProcessor(TerseConsoleSpanExporter()))

    if settings.otel_exporter_otlp_endpoint:
        otlp_exporter = OTLPSpanExporter(endpoint=settings.otel_exporter_otlp_endpoint)
        provider.add_span_processor(BatchSpanProcessor(otlp_exporter))

    trace.set_tracer_provider(provider)
    FastAPIInstrumentor.instrument_app(app)

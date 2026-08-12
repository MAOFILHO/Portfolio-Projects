"""OpenTelemetry wiring.

Set up before any pipeline logic so every step is traced. Spans are printed to
the terminal during execution — not only shipped to the portal — because a trace
you cannot see while developing is a trace you will not use.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    SimpleSpanProcessor,
    SpanExporter,
    SpanExportResult,
)

from app.config import get_settings

_LOGGER = logging.getLogger("foundry.telemetry")
_INITIALISED = False


class _CompactConsoleExporter(SpanExporter):
    """One readable line per span instead of a wall of JSON.

    The stock ConsoleSpanExporter dumps the full span as JSON, which drowns the
    run output. This keeps traces glanceable while work is happening.
    """

    def export(self, spans: Any) -> SpanExportResult:
        for span in spans:
            duration_ms = (span.end_time - span.start_time) / 1_000_000
            attrs = {k: v for k, v in (span.attributes or {}).items() if not k.startswith("otel.")}
            detail = " ".join(f"{k}={v}" for k, v in list(attrs.items())[:4])
            _LOGGER.info("⎡trace⎤ %-38s %7.1fms %s", span.name, duration_ms, detail)
        return SpanExportResult.SUCCESS

    def force_flush(self, timeout_millis: int = 30_000) -> bool:
        return True

    def shutdown(self) -> None:
        return None


def init_telemetry(force: bool = False) -> trace.Tracer:
    """Initialise the tracer provider once and return a tracer."""
    global _INITIALISED
    settings = get_settings()

    if _INITIALISED and not force:
        return trace.get_tracer(settings.otel_service_name)

    provider = TracerProvider(
        resource=Resource.create(
            {
                "service.name": settings.otel_service_name,
                "service.version": "0.1.0",
                "deployment.environment": settings.demo_mode,
            }
        )
    )

    if settings.otel_console_export:
        provider.add_span_processor(SimpleSpanProcessor(_CompactConsoleExporter()))

    if settings.applicationinsights_connection_string:
        try:
            from azure.monitor.opentelemetry.exporter import AzureMonitorTraceExporter

            provider.add_span_processor(
                BatchSpanProcessor(
                    AzureMonitorTraceExporter(
                        connection_string=settings.applicationinsights_connection_string
                    )
                )
            )
            _LOGGER.info("Application Insights exporter enabled")
        except Exception as exc:  # pragma: no cover - optional dependency path
            _LOGGER.warning("Application Insights exporter unavailable: %s", exc)

    trace.set_tracer_provider(provider)
    _INITIALISED = True
    return trace.get_tracer(settings.otel_service_name)


def get_tracer() -> trace.Tracer:
    return init_telemetry()


@contextmanager
def span(name: str, **attributes: Any) -> Iterator[trace.Span]:
    """Convenience span context manager that records exceptions."""
    tracer = get_tracer()
    with tracer.start_as_current_span(name) as current:
        for key, value in attributes.items():
            if value is not None:
                current.set_attribute(key, value)
        try:
            yield current
        except Exception as exc:
            current.record_exception(exc)
            current.set_status(trace.Status(trace.StatusCode.ERROR, str(exc)))
            raise

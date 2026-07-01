"""OpenTelemetry + Azure Monitor exporter configuration.

This module configures distributed tracing for the CDSS backend. It exports
traces to Azure Application Insights using the connection string from the
deployed App Insights resource.

Usage:
    Set these env vars on the Container App:
        CDSS_OTEL_ENABLED=true
        APPLICATIONINSIGHTS_CONNECTION_STRING=<from deployment>

    Then call setup_telemetry() during FastAPI app startup.
"""

from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)


def setup_telemetry() -> bool:
    conn_string = os.environ.get("APPLICATIONINSIGHTS_CONNECTION_STRING", "")
    if not conn_string:
        logger.warning("APPLICATIONINSIGHTS_CONNECTION_STRING not set — telemetry disabled")
        return False

    try:
        from opentelemetry import trace
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from azure.monitor.opentelemetry.exporter import AzureMonitorTraceExporter

        resource = Resource.create({
            "service.name": "cdss-agentic-rag",
            "service.version": "1.0.0",
        })

        tracer_provider = TracerProvider(resource=resource)

        exporter = AzureMonitorTraceExporter(connection_string=conn_string)
        tracer_provider.add_span_processor(BatchSpanProcessor(exporter))

        trace.set_tracer_provider(tracer_provider)

        logger.info("OpenTelemetry + Azure Monitor telemetry configured")
        return True

    except ImportError:
        logger.warning(
            "OpenTelemetry or Azure Monitor exporter not installed. "
            "Install with: pip install azure-cdss-pipeline[observability]"
        )
        return False
    except Exception:
        logger.exception("Failed to configure telemetry")
        return False

"""Auto-instrument FastAPI, httpx, and Azure SDK for distributed tracing.

Call setup_observability(app) during FastAPI startup to enable:
- Request/response tracing for all API endpoints
- Outbound HTTP tracing for PubMed, OpenFDA, RxNorm, DrugBank
- Custom span attributes for clinical domain context
"""

from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)


def setup_observability(app) -> bool:
    if not os.environ.get("CDSS_OTEL_ENABLED", "").lower() in ("true", "1", "yes"):
        return False

    from cdss_deploy.observability.setup import setup_telemetry

    if not setup_telemetry():
        return False

    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

        FastAPIInstrumentor.instrument_app(app)
        logger.info("FastAPI instrumented with OpenTelemetry")
    except ImportError:
        logger.warning("opentelemetry-instrumentation-fastapi not installed")
    except Exception:
        logger.exception("Failed to instrument FastAPI")

    try:
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

        HTTPXClientInstrumentor().instrument()
        logger.info("httpx instrumented with OpenTelemetry")
    except ImportError:
        logger.debug("opentelemetry-instrumentation-httpx not installed")
    except Exception:
        logger.exception("Failed to instrument httpx")

    return True

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.alerts.queue_consumer import run_queue_consumer
from app.alerts.ws_manager import manager
from app.config import get_settings
from app.deps import get_storage
from app.routes import agents, audit, clips, events, frames, health, observability, query, ws
from app.routes import settings as settings_route

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("surveil.main")

_stop_event = asyncio.Event()


def _configure_observability() -> None:
    settings = get_settings()
    if not settings.applicationinsights_connection_string:
        logger.info("APPLICATIONINSIGHTS_CONNECTION_STRING not set — skipping telemetry export")
        return
    try:
        from azure.monitor.opentelemetry import configure_azure_monitor

        configure_azure_monitor(connection_string=settings.applicationinsights_connection_string)
        logger.info("Application Insights telemetry export configured")
    except Exception:
        logger.exception("Failed to configure Application Insights telemetry (continuing without it)")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    logger.info("Starting Azure Real-Time Surveillance backend")
    logger.info("Watching for tags: %s (min_confidence=%.2f, min_count=%d)",
                settings.watch_tags_list(), settings.alert_min_confidence, settings.alert_min_count)

    _stop_event.clear()
    consumer_task = asyncio.create_task(run_queue_consumer(get_storage(), manager, _stop_event))
    try:
        yield
    finally:
        logger.info("Shutting down: stopping alert queue consumer")
        _stop_event.set()
        await consumer_task


def create_app() -> FastAPI:
    _configure_observability()
    settings = get_settings()
    app = FastAPI(
        title="Azure Real-Time Surveillance API",
        description="Frame ingest, event history, and real-time alert streaming.",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def default_no_store_cache(request, call_next):
        # Every list/status endpoint here is dynamic and must never be served
        # stale from the browser's HTTP cache (e.g. Event History looking
        # empty right after sign-in until a manual refresh forces a fresh
        # fetch). The frame/clip proxy endpoints are the deliberate exception
        # -- they already set their own long-lived Cache-Control since that
        # content is immutable -- so this only fills in the header when one
        # isn't already present, never overrides it.
        response = await call_next(request)
        if "cache-control" not in response.headers:
            response.headers["Cache-Control"] = "no-store"
        return response

    app.include_router(health.router)
    app.include_router(frames.router)
    app.include_router(clips.router)
    app.include_router(events.router)
    app.include_router(query.router)
    app.include_router(agents.router)
    app.include_router(settings_route.router)
    app.include_router(audit.router)
    app.include_router(observability.router)
    app.include_router(ws.router)

    return app


app = create_app()

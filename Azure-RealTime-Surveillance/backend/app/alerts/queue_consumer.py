"""Background task: polls the 'alerts' Storage Queue (populated by the Azure
Function analysis worker) and fans each alert out to connected WebSocket
dashboards. This is the decoupling point between the Function and the API —
see docs/architecture.md for why a queue is used instead of a direct call.
"""

from __future__ import annotations

import asyncio
import logging

from surveil_core.storage import SurveillanceStorage

from app.alerts.ws_manager import AlertConnectionManager

logger = logging.getLogger("surveil.queue_consumer")

POLL_INTERVAL_SECONDS = 2


async def run_queue_consumer(storage: SurveillanceStorage, manager: AlertConnectionManager, stop_event: asyncio.Event) -> None:
    logger.info("Alert queue consumer started (polling every %ss)", POLL_INTERVAL_SECONDS)
    while not stop_event.is_set():
        try:
            messages = await asyncio.to_thread(lambda: list(storage.receive_alerts(max_messages=8)))
            for message in messages:
                await manager.broadcast(message.content)
                await asyncio.to_thread(storage.delete_alert_message, message)
        except Exception:
            logger.exception("Alert queue consumer iteration failed; will retry")

        try:
            await asyncio.wait_for(stop_event.wait(), timeout=POLL_INTERVAL_SECONDS)
        except asyncio.TimeoutError:
            pass
    logger.info("Alert queue consumer stopped")

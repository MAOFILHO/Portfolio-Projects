from __future__ import annotations

import logging

from fastapi import WebSocket

logger = logging.getLogger("surveil.ws")


class AlertConnectionManager:
    """Tracks connected dashboard WebSocket clients and fans out alert JSON."""

    def __init__(self) -> None:
        self._connections: set[WebSocket] = set()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections.add(websocket)
        logger.info("WebSocket connected (%d total)", len(self._connections))

    def disconnect(self, websocket: WebSocket) -> None:
        self._connections.discard(websocket)
        logger.info("WebSocket disconnected (%d total)", len(self._connections))

    async def broadcast(self, message: str) -> None:
        dead: list[WebSocket] = []
        for connection in self._connections:
            try:
                await connection.send_text(message)
            except Exception:
                dead.append(connection)
        for connection in dead:
            self.disconnect(connection)


manager = AlertConnectionManager()

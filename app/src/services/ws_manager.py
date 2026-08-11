"""WebSocket connection manager for real-time backend job monitoring."""

import logging
from collections import deque
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages active WebSocket connections, maintains 5-job event history, and broadcasts real-time events."""

    def __init__(self) -> None:
        self.active_connections: set[WebSocket] = set()
        self.event_history: deque[dict[str, Any]] = deque(maxlen=150)
        self.job_ids_in_history: deque[int] = deque(maxlen=5)

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active_connections.add(websocket)
        logger.info("WebSocket client connected. Active connections: %d", len(self.active_connections))

        # Replay event history for the last 5 jobs upon connection
        if self.event_history:
            try:
                await websocket.send_json({
                    "type": "history",
                    "events": list(self.event_history),
                })
            except Exception as exc:  # noqa: BLE001
                logger.warning("Failed to send history to new WebSocket client: %s", exc)

    def disconnect(self, websocket: WebSocket) -> None:
        self.active_connections.discard(websocket)
        logger.info("WebSocket client disconnected. Active connections: %d", len(self.active_connections))

    async def broadcast(self, message: dict[str, Any]) -> None:
        import time
        if "timestamp" not in message:
            message["timestamp"] = time.strftime("%H:%M:%S")

        if isinstance(message, dict) and message.get("type") in ("stage_update", "job_queued", "job_started", "job_completed", "job_failed"):
            self.event_history.append(message)
            job_id = message.get("job_id")
            if job_id and job_id not in self.job_ids_in_history:
                self.job_ids_in_history.append(job_id)
                # Keep events for the last 5 jobs
                valid_job_ids = set(self.job_ids_in_history)
                trimmed_events = [e for e in self.event_history if e.get("job_id") in valid_job_ids or not e.get("job_id")]
                self.event_history = deque(trimmed_events, maxlen=150)

        if not self.active_connections:
            return

        disconnected = set()
        for connection in list(self.active_connections):
            try:
                await connection.send_json(message)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Failed to send message to WebSocket client: %s", exc)
                disconnected.add(connection)

        for conn in disconnected:
            self.disconnect(conn)


# Global singleton instance
ws_manager = ConnectionManager()

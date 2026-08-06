"""
PrintBar Backend — WebSocket Connection Manager

Manages persistent WebSocket connections from Raspberry Pi kiosks.

Architecture:
    - Each kiosk maintains ONE persistent WebSocket connection.
    - The backend pushes jobs to kiosks via WebSocket messages.
    - Kiosks send heartbeat messages every 30 seconds.
    - If no heartbeat within 90s, the kiosk is marked OFFLINE.

Message protocol (JSON):
    Backend → Kiosk:
        {"type": "JOB_ASSIGNED", "data": {...}}
        {"type": "JOB_CANCELLED", "data": {"jobId": "..."}}
        {"type": "PING", "data": {}}

    Kiosk → Backend:
        {"type": "HEARTBEAT", "data": {"cpuPercent": 45.2, ...}}
        {"type": "JOB_STATUS", "data": {"jobId": "...", "status": "PRINTING"}}
        {"type": "JOB_COMPLETED", "data": {"jobId": "..."}}
        {"type": "JOB_FAILED", "data": {"jobId": "...", "reason": "..."}}
        {"type": "PONG", "data": {}}
"""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime

from fastapi import WebSocket

from app.core.logging import get_logger

logger = get_logger(__name__)


class KioskConnection:
    """Represents a single active WebSocket connection from a kiosk."""

    __slots__ = ("kiosk_id", "websocket", "connected_at", "last_heartbeat")

    def __init__(self, kiosk_id: str, websocket: WebSocket) -> None:
        self.kiosk_id = kiosk_id
        self.websocket = websocket
        self.connected_at = datetime.now(tz=UTC)
        self.last_heartbeat = datetime.now(tz=UTC)

    async def send(self, message_type: str, data: dict) -> bool:
        """
        Sends a JSON message to this kiosk.

        Returns:
            True if sent successfully, False if connection is broken.
        """
        try:
            payload = json.dumps(
                {
                    "type": message_type,
                    "data": data,
                    "timestamp": datetime.now(tz=UTC).isoformat(),
                }
            )
            await self.websocket.send_text(payload)
            return True
        except Exception as exc:
            logger.warning(
                "ws_send_failed",
                kiosk_id=self.kiosk_id,
                message_type=message_type,
                error=str(exc),
            )
            return False


class WebSocketManager:
    """
    Manages all active WebSocket connections.

    Thread-safe for async use with asyncio.Lock.
    One connection per kiosk — reconnection replaces the old connection.
    """

    def __init__(self) -> None:
        # kiosk_id → KioskConnection
        self._connections: dict[str, KioskConnection] = {}
        self._lock = asyncio.Lock()

    async def connect(self, kiosk_id: str, websocket: WebSocket) -> None:
        """
        Registers a new WebSocket connection from a kiosk.

        If the kiosk already has an active connection, it is replaced.
        """
        await websocket.accept()

        async with self._lock:
            # Close existing connection if any.
            if kiosk_id in self._connections:
                old = self._connections[kiosk_id]
                try:
                    await old.websocket.close(code=1001)
                except Exception:
                    pass

            self._connections[kiosk_id] = KioskConnection(kiosk_id, websocket)

        logger.info("ws_kiosk_connected", kiosk_id=kiosk_id, total=len(self._connections))

    async def disconnect(self, kiosk_id: str) -> None:
        """Removes a kiosk connection on disconnect."""
        async with self._lock:
            self._connections.pop(kiosk_id, None)

        logger.info("ws_kiosk_disconnected", kiosk_id=kiosk_id, total=len(self._connections))

    async def send_to_kiosk(self, kiosk_id: str, message_type: str, data: dict) -> bool:
        """
        Sends a message to a specific kiosk.

        Returns:
            True if sent, False if kiosk not connected.
        """
        conn = self._connections.get(kiosk_id)
        if not conn:
            logger.warning("ws_kiosk_not_connected", kiosk_id=kiosk_id)
            return False
        return await conn.send(message_type, data)

    async def broadcast(self, message_type: str, data: dict) -> int:
        """
        Broadcasts a message to all connected kiosks.

        Returns:
            Number of kiosks successfully reached.
        """
        sent = 0
        for conn in list(self._connections.values()):
            if await conn.send(message_type, data):
                sent += 1
        return sent

    def is_connected(self, kiosk_id: str) -> bool:
        return kiosk_id in self._connections

    def connected_kiosk_ids(self) -> list[str]:
        return list(self._connections.keys())

    def update_heartbeat(self, kiosk_id: str) -> None:
        if conn := self._connections.get(kiosk_id):
            conn.last_heartbeat = datetime.now(tz=UTC)

    async def broadcast_to_all(self, message_type: str, data: dict) -> int:
        """Alias for broadcast — sends to all connected kiosks."""
        return await self.broadcast(message_type, data)

    async def ping_all(self) -> None:
        """Sends PING to all connected kiosks. Used by background keepalive worker."""
        await self.broadcast("PING", {"serverTime": datetime.now(tz=UTC).isoformat()})


# Module-level singleton — shared across all WebSocket routes.
ws_manager = WebSocketManager()

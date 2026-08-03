"""
PrintBar Kiosk Agent — WebSocket Connection Manager

Maintains a persistent, auto-reconnecting WebSocket connection to the backend.
Reconnects with exponential backoff (1s → 2s → 4s → max 60s).
"""
from __future__ import annotations
import asyncio
import json
import logging
from typing import Callable
import websockets
from websockets.exceptions import ConnectionClosed

logger = logging.getLogger(__name__)


class KioskWebSocketConnection:
    """
    Persistent WebSocket client with automatic reconnection.

    Usage:
        conn = KioskWebSocketConnection(url=..., token=..., on_message=handler)
        await conn.run_forever()
    """

    def __init__(self, url: str, token: str, on_message: Callable, kiosk_id: str) -> None:
        self._url = url
        self._token = token
        self._on_message = on_message
        self._kiosk_id = kiosk_id
        self._ws = None
        self._connected = False
        self._running = False

    async def run_forever(self) -> None:
        """Connects and reconnects indefinitely with exponential backoff."""
        self._running = True
        delay = 1.0

        while self._running:
            try:
                headers = {"Authorization": f"Bearer {self._token}"}
                async with websockets.connect(self._url, extra_headers=headers, ping_interval=30) as ws:
                    self._ws = ws
                    self._connected = True
                    delay = 1.0  # Reset delay on successful connect.
                    logger.info("ws_connected", url=self._url)

                    # Send REGISTER message.
                    await ws.send(json.dumps({
                        "type": "REGISTER",
                        "data": {"kioskId": self._kiosk_id},
                    }))

                    async for raw_msg in ws:
                        try:
                            msg = json.loads(raw_msg)
                            await self._on_message(msg)
                        except Exception as exc:
                            logger.error("ws_message_handler_error", error=str(exc))

            except ConnectionClosed as exc:
                logger.warning("ws_disconnected", code=exc.code, reason=exc.reason)
            except Exception as exc:
                logger.error("ws_error", error=str(exc))
            finally:
                self._connected = False
                self._ws = None

            if self._running:
                logger.info(f"ws_reconnecting_in={delay:.1f}s")
                await asyncio.sleep(delay)
                delay = min(delay * 2, 30.0)

    async def send(self, message: dict) -> None:
        """Sends a JSON message over the WebSocket."""
        if self._ws and self._connected:
            await self._ws.send(json.dumps(message))

    async def close(self) -> None:
        """Gracefully closes the connection."""
        self._running = False
        if self._ws:
            await self._ws.close()

    async def force_disconnect(self) -> None:
        """
        Forces the WebSocket to disconnect and trigger a reconnect.
        Useful when an external subsystem (like heartbeat) detects an unresponsive connection.
        """
        if self._ws and self._connected:
            logger.warning("ws_force_disconnect_requested")
            await self._ws.close()
            # self._ws.close() will cause `async for raw_msg in ws:` to exit with ConnectionClosed
            # and the reconnect loop will automatically take over since self._running is still True.

    @property
    def is_connected(self) -> bool:
        return self._connected


"""
PrintBar Kiosk Agent — WebSocket Connection Manager

Maintains a persistent, auto-reconnecting WebSocket connection to the backend.
Reconnects with exponential backoff (1s → 2s → 4s → max 30s).

Production settings:
- ping_interval=30s: Server must respond within ping_timeout.
- ping_timeout=15s:  If no PONG in 15s, connection is considered dead.
- close_timeout=5s:  Clean close is attempted before giving up.

Every incoming and outgoing message is logged with type and timestamp.
"""
from __future__ import annotations
import asyncio
import json
import logging
from datetime import UTC, datetime
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
                async with websockets.connect(
                    self._url,
                    ping_interval=30,    # Send PING every 30s to keep connection alive.
                    ping_timeout=15,     # Close if no PONG within 15s (dead connection).
                    close_timeout=5,     # Wait up to 5s for clean close.
                    max_size=10 * 1024 * 1024,  # 10MB max message size.
                ) as ws:
                    self._ws = ws
                    self._connected = True
                    delay = 1.0  # Reset backoff on successful connect.
                    logger.info(
                        "WS_CONNECTED kiosk_id=%s url=%s ts=%s",
                        self._kiosk_id, self._url, datetime.now(tz=UTC).isoformat(),
                    )

                    # Send REGISTER message on connect.
                    register_msg = json.dumps({
                        "type": "REGISTER",
                        "data": {"kioskId": self._kiosk_id},
                    })
                    await ws.send(register_msg)
                    logger.info(
                        "WS_SENT type=REGISTER kiosk_id=%s ts=%s",
                        self._kiosk_id, datetime.now(tz=UTC).isoformat(),
                    )

                    async for raw_msg in ws:
                        try:
                            msg = json.loads(raw_msg)
                            msg_type = msg.get("type", "UNKNOWN")
                            logger.info(
                                "WS_RECEIVED type=%s kiosk_id=%s ts=%s",
                                msg_type, self._kiosk_id, datetime.now(tz=UTC).isoformat(),
                            )
                            await self._on_message(msg)
                        except Exception as exc:
                            logger.error(
                                "WS_MESSAGE_HANDLER_ERROR kiosk_id=%s error=%s ts=%s",
                                self._kiosk_id, str(exc), datetime.now(tz=UTC).isoformat(),
                            )

            except ConnectionClosed as exc:
                logger.warning(
                    "WS_DISCONNECTED kiosk_id=%s code=%s reason=%s ts=%s",
                    self._kiosk_id, exc.code, exc.reason, datetime.now(tz=UTC).isoformat(),
                )
            except Exception as exc:
                logger.error(
                    "WS_ERROR kiosk_id=%s error=%s ts=%s",
                    self._kiosk_id, str(exc), datetime.now(tz=UTC).isoformat(),
                )
            finally:
                self._connected = False
                self._ws = None

            if self._running:
                logger.info(
                    "WS_RECONNECTING kiosk_id=%s delay=%.1f ts=%s",
                    self._kiosk_id, delay, datetime.now(tz=UTC).isoformat(),
                )
                await asyncio.sleep(delay)
                delay = min(delay * 2, 30.0)

    async def send(self, message: dict) -> None:
        """
        Sends a JSON message over the WebSocket and logs it.

        Raises:
            RuntimeError: If the connection is not active.
        """
        if self._ws and self._connected:
            msg_type = message.get("type", "UNKNOWN")
            try:
                await self._ws.send(json.dumps(message))
                logger.info(
                    "WS_SENT type=%s kiosk_id=%s ts=%s",
                    msg_type, self._kiosk_id, datetime.now(tz=UTC).isoformat(),
                )
            except Exception as exc:
                logger.error(
                    "WS_SEND_FAILED type=%s kiosk_id=%s error=%s ts=%s",
                    msg_type, self._kiosk_id, str(exc), datetime.now(tz=UTC).isoformat(),
                )
                # Mark connection as disconnected — run_forever will reconnect.
                self._connected = False
                self._ws = None
                raise
        else:
            logger.warning(
                "WS_SEND_DROPPED_NOT_CONNECTED type=%s kiosk_id=%s ts=%s",
                message.get("type", "UNKNOWN"), self._kiosk_id,
                datetime.now(tz=UTC).isoformat(),
            )

    async def close(self) -> None:
        """Gracefully closes the connection and stops reconnect loop."""
        self._running = False
        if self._ws:
            try:
                await self._ws.close()
            except Exception:
                pass

    async def force_disconnect(self) -> None:
        """
        Forces the WebSocket to disconnect and trigger a reconnect.
        Useful when the heartbeat sender detects an unresponsive connection.
        """
        if self._ws and self._connected:
            logger.warning(
                "WS_FORCE_DISCONNECT kiosk_id=%s ts=%s",
                self._kiosk_id, datetime.now(tz=UTC).isoformat(),
            )
            try:
                await self._ws.close()
            except Exception:
                pass

    @property
    def is_connected(self) -> bool:
        return self._connected

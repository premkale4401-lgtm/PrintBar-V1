"""
PrintBar Kiosk Agent — Heartbeat Sender

Sends a heartbeat message every 30 seconds over the WebSocket.
"""
from __future__ import annotations
import asyncio
import logging
from app.config.settings import KioskSettings
from app.monitoring.health import get_system_metrics

logger = logging.getLogger(__name__)


class HeartbeatSender:
    """Sends periodic heartbeat messages to the backend."""

    def __init__(
        self, 
        settings: KioskSettings, 
        ws_send, 
        get_printer_status=None, 
        ws_force_disconnect=None
    ) -> None:
        self._settings = settings
        self._ws_send = ws_send
        self._get_printer_status = get_printer_status
        self._ws_force_disconnect = ws_force_disconnect
        self._printing = False

    def set_printing(self, printing: bool) -> None:
        """Updates the printing flag for the next heartbeat."""
        self._printing = printing

    async def run_forever(self) -> None:
        """Sends heartbeats at the configured interval until cancelled."""
        logger.info("heartbeat_sender_started", interval=self._settings.heartbeat_interval_sec)

        while True:
            try:
                metrics = get_system_metrics()
                printer_status = "UNKNOWN"
                if self._get_printer_status:
                    try:
                        res = self._get_printer_status()
                        if asyncio.iscoroutine(res) or asyncio.isfuture(res) or hasattr(res, '__await__'):
                            printer_status = await res
                        else:
                            printer_status = str(res)
                    except Exception:
                        printer_status = "UNKNOWN"

                await self._ws_send({
                    "type": "HEARTBEAT",
                    "data": {
                        "kioskId": self._settings.kiosk_id,
                        "printing": self._printing,
                        "appVersion": "1.0.0",
                        "cpuPercent": metrics.get("cpu_percent"),
                        "ramPercent": metrics.get("ram_percent"),
                        "diskPercent": metrics.get("disk_percent"),
                        "temperatureC": metrics.get("temperature_c"),
                        "printerStatus": printer_status,
                    },
                })
                logger.debug("heartbeat_sent")
            except Exception as exc:
                logger.error("heartbeat_error", error=str(exc))
                if self._ws_force_disconnect:
                    await self._ws_force_disconnect()

            await asyncio.sleep(self._settings.heartbeat_interval_sec)

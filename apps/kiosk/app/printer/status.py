"""
PrintBar Kiosk Agent — Printer Status Poller

Polls CUPS for printer health and reports to the kiosk agent.
"""
from __future__ import annotations
import asyncio
import logging
from app.printer.cups_adapter import CupsAdapter

logger = logging.getLogger(__name__)


class PrinterStatusPoller:
    """Polls CUPS printer status on a timer."""

    def __init__(self, adapter: CupsAdapter, interval_sec: int = 60) -> None:
        self._adapter = adapter
        self._interval = interval_sec
        self._current_status = "OFFLINE"

    @property
    def status(self) -> str:
        return self._current_status

    async def run_forever(self) -> None:
        """Polls printer status at the configured interval."""
        while True:
            try:
                self._current_status = self._adapter.get_printer_status()
                logger.debug("printer_status_polled", status=self._current_status)
            except Exception as exc:
                logger.error("printer_status_poll_error", error=str(exc))
                self._current_status = "OFFLINE"
            await asyncio.sleep(self._interval)

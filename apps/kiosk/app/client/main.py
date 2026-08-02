"""
PrintBar Kiosk Agent — Main Orchestrator

Wires together:
    - Authenticator
    - WebSocketConnection
    - HeartbeatSender
    - JobHandler
    - PrinterStatusPoller
"""
from __future__ import annotations
import asyncio
import logging
from app.auth.authenticator import Authenticator
from app.config.settings import KioskSettings
from app.heartbeat.sender import HeartbeatSender
from app.jobs.downloader import JobDownloader
from app.jobs.handler import JobHandler
from app.printer.cups_adapter import CupsAdapter
from app.printer.status import PrinterStatusPoller
from app.websocket.connection import KioskWebSocketConnection

logger = logging.getLogger(__name__)


class KioskClient:
    """Top-level kiosk agent that orchestrates all subsystems."""

    def __init__(self, settings: KioskSettings) -> None:
        self._settings = settings
        self._auth = Authenticator(settings)
        self._printer = CupsAdapter(settings.cups_printer_name)
        self._downloader = JobDownloader(settings)
        self._ws: KioskWebSocketConnection | None = None
        self._heartbeat: HeartbeatSender | None = None

    async def run(self) -> None:
        """Main run loop — authenticates, then runs all subsystems concurrently."""
        logger.info("kiosk_client_run_start")

        # Authenticate and get JWT.
        token = await self._auth.authenticate()

        # Build WS connection.
        self._ws = KioskWebSocketConnection(
            url=self._settings.ws_url,
            token=token,
            on_message=self._on_ws_message,
            kiosk_id=self._settings.kiosk_id,
        )

        # Job handler.
        job_handler = JobHandler(
            settings=self._settings,
            downloader=self._downloader,
            printer=self._printer,
            auth_headers_fn=self._auth.authorization_header,
            ws_send=self._ws.send,
            set_printing_fn=lambda v: None,  # wired below
        )

        # Heartbeat sender.
        status_poller = PrinterStatusPoller(self._printer)
        self._heartbeat = HeartbeatSender(
            settings=self._settings,
            ws_send=self._ws.send,
            get_printer_status=lambda: status_poller.status,
        )

        # Wire printing flag.
        job_handler._set_printing = self._heartbeat.set_printing

        # Run all subsystems concurrently.
        await asyncio.gather(
            self._ws.run_forever(),
            self._heartbeat.run_forever(),
            status_poller.run_forever(),
        )

    async def _on_ws_message(self, msg: dict) -> None:
        """Dispatches incoming WebSocket messages to the appropriate handler."""
        msg_type = msg.get("type", "")
        data = msg.get("data", {})

        if msg_type == "NEW_JOB":
            logger.info("ws_new_job_received", job_id=data.get("jobId"))
            if self._ws:
                handler = JobHandler(
                    settings=self._settings,
                    downloader=self._downloader,
                    printer=self._printer,
                    auth_headers_fn=self._auth.authorization_header,
                    ws_send=self._ws.send,
                    set_printing_fn=self._heartbeat.set_printing if self._heartbeat else lambda v: None,
                )
                asyncio.create_task(handler.handle_new_job(data))

        elif msg_type == "CANCEL":
            logger.info("ws_cancel_received", job_id=data.get("jobId"))

        elif msg_type == "PING":
            if self._ws:
                await self._ws.send({"type": "PONG", "data": {}})

        elif msg_type == "TEST_PRINT":
            logger.info("ws_test_print_received")
            status = self._printer.get_printer_status()
            logger.info("test_print_printer_status", status=status)

        else:
            logger.warning("ws_unknown_message_type", type=msg_type)

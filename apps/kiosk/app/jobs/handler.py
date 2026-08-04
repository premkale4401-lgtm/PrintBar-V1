"""
PrintBar Kiosk Agent — Job Handler

Receives JOB_ASSIGNED WebSocket messages, requests a signed download URL via
DOWNLOAD_URL_REQUEST → DOWNLOAD_URL, downloads the PDF, prints it via CUPS,
and reports job status transitions back to the backend.

WebSocket Protocol (Kiosk → Backend):
    JOB_STATUS      — intermediate status update (DOWNLOADING, PRINTING)
    JOB_COMPLETED   — job finished successfully (triggers file cleanup)
    JOB_FAILED      — job failed (triggers failure record)

WebSocket Protocol (Kiosk → Backend):
    DOWNLOAD_URL_REQUEST — request a signed download URL for a job
"""
from __future__ import annotations
import asyncio
import logging
from datetime import UTC, datetime
from app.config.settings import KioskSettings
from app.jobs.downloader import JobDownloader
from app.printer.cups_adapter import CupsAdapter

logger = logging.getLogger(__name__)


class JobHandler:
    """Handles the full lifecycle of a print job."""

    def __init__(
        self,
        settings: KioskSettings,
        downloader: JobDownloader,
        printer: CupsAdapter,
        auth_headers_fn,
        ws_send,
        set_printing_fn,
    ) -> None:
        self._settings = settings
        self._downloader = downloader
        self._printer = printer
        self._auth_headers_fn = auth_headers_fn
        self._ws_send = ws_send
        self._set_printing = set_printing_fn
        self._active_job_id: str | None = None
        self._processed_job_ids: list[str] = []
        self._lock = asyncio.Lock()
        self._pending_download_futures: dict[str, asyncio.Future[str]] = {}

    def resolve_download_url(self, job_id: str, url: str) -> None:
        """Called when a DOWNLOAD_URL message is received for this job_id."""
        fut = self._pending_download_futures.get(job_id)
        if fut and not fut.done():
            logger.info(
                "DOWNLOAD_URL_RECEIVED job_id=%s url_len=%d ts=%s",
                job_id, len(url), datetime.now(tz=UTC).isoformat(),
            )
            fut.set_result(url)
        else:
            logger.warning(
                "DOWNLOAD_URL_RECEIVED_NO_WAITER job_id=%s ts=%s",
                job_id, datetime.now(tz=UTC).isoformat(),
            )

    def reject_download_url(self, job_id: str, error: str) -> None:
        """Called when a DOWNLOAD_URL_ERROR message is received for this job_id."""
        fut = self._pending_download_futures.get(job_id)
        if fut and not fut.done():
            logger.error(
                "DOWNLOAD_URL_ERROR job_id=%s error=%s ts=%s",
                job_id, error, datetime.now(tz=UTC).isoformat(),
            )
            fut.set_exception(RuntimeError(f"Download URL request failed: {error}"))

    async def handle_new_job(self, job_data: dict) -> None:
        """
        Full job lifecycle:
            JOB_ASSIGNED_RECEIVED
            → DOWNLOAD_URL_REQUEST_SENT
            → DOWNLOAD_URL_RECEIVED
            → DOWNLOAD_STARTED
            → DOWNLOAD_COMPLETED
            → SHA_VERIFIED
            → PRINT_STARTED
            → CUPS_JOB_ID
            → PRINT_COMPLETED
            → JOB_STATUS_SENT (COMPLETED or FAILED)
            → JOB_COMPLETED_SENT or JOB_FAILED_SENT
            → CLEANUP_COMPLETED

        Args:
            job_data: Payload from the JOB_ASSIGNED WebSocket message.
        """
        job_id = job_data.get("jobId")
        kiosk_id = self._settings.kiosk_id
        ts = datetime.now(tz=UTC).isoformat()

        if not job_id:
            logger.error("JOB_ASSIGNED_MISSING_JOB_ID ts=%s", ts)
            return

        logger.info(
            "JOB_ASSIGNED_RECEIVED job_id=%s kiosk_id=%s ts=%s",
            job_id, kiosk_id, ts,
        )

        async with self._lock:
            if job_id in self._processed_job_ids:
                logger.info(
                    "DUPLICATE_JOB_IGNORED job_id=%s kiosk_id=%s ts=%s",
                    job_id, kiosk_id, datetime.now(tz=UTC).isoformat(),
                )
                return

            self._processed_job_ids.append(job_id)
            if len(self._processed_job_ids) > 100:
                self._processed_job_ids.pop(0)

            self._active_job_id = job_id
            self._set_printing(True)
            pdf_path: str | None = None
            start_time = asyncio.get_running_loop().time()

            try:
                # 1. Report DOWNLOADING status.
                await self._report_status(job_id, "DOWNLOADING")

                # 2. Request a signed download URL via WebSocket.
                download_url = await self._get_download_url(job_id)
                expected_sha256 = job_data.get("sha256")
                expected_size = job_data.get("fileSize")

                # 3. Download PDF.
                logger.info(
                    "DOWNLOAD_STARTED job_id=%s kiosk_id=%s url_len=%d ts=%s",
                    job_id, kiosk_id, len(download_url), datetime.now(tz=UTC).isoformat(),
                )
                pdf_path = await self._downloader.download(
                    job_id, download_url, expected_sha256, expected_size
                )
                logger.info(
                    "DOWNLOAD_COMPLETED job_id=%s kiosk_id=%s path=%s ts=%s",
                    job_id, kiosk_id, pdf_path, datetime.now(tz=UTC).isoformat(),
                )

                if expected_sha256:
                    logger.info(
                        "SHA_VERIFIED job_id=%s kiosk_id=%s sha256=%s ts=%s",
                        job_id, kiosk_id, expected_sha256, datetime.now(tz=UTC).isoformat(),
                    )

                # 4. Print via CUPS.
                await self._report_status(job_id, "PRINTING")
                logger.info(
                    "PRINT_STARTED job_id=%s kiosk_id=%s copies=%s color=%s ts=%s",
                    job_id, kiosk_id,
                    job_data.get("copies", 1),
                    job_data.get("colorMode", "BW"),
                    datetime.now(tz=UTC).isoformat(),
                )

                cups_job_id = self._printer.submit_job(
                    pdf_path,
                    copies=job_data.get("copies", 1),
                    color_mode=job_data.get("colorMode", "BW"),
                    duplex=job_data.get("duplex", False),
                    paper_size=job_data.get("paperSize", "A4"),
                )
                logger.info(
                    "CUPS_JOB_ID job_id=%s kiosk_id=%s cups_job_id=%s ts=%s",
                    job_id, kiosk_id, cups_job_id, datetime.now(tz=UTC).isoformat(),
                )

                # 5. Wait for CUPS to finish (runs in thread pool to avoid blocking event loop).
                success = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: self._printer.wait_for_completion(
                        cups_job_id, self._settings.print_timeout_sec
                    ),
                )

                duration = asyncio.get_running_loop().time() - start_time
                pages = job_data.get("totalPages", job_data.get("pagesSelected", "unknown"))

                if success:
                    logger.info(
                        "PRINT_COMPLETED job_id=%s kiosk_id=%s duration=%.1f pages=%s ts=%s",
                        job_id, kiosk_id, duration, pages, datetime.now(tz=UTC).isoformat(),
                    )
                    await self._report_status(job_id, "COMPLETED")
                    await self._report_completed(job_id)
                else:
                    logger.error(
                        "PRINT_FAILED job_id=%s kiosk_id=%s duration=%.1f pages=%s ts=%s",
                        job_id, kiosk_id, duration, pages, datetime.now(tz=UTC).isoformat(),
                    )
                    await self._report_status(job_id, "FAILED", error="Print job did not complete successfully.")
                    await self._report_failed(job_id, "CUPS_JOB_INCOMPLETE")

            except Exception as exc:
                duration = asyncio.get_running_loop().time() - start_time
                pages = job_data.get("totalPages", job_data.get("pagesSelected", "unknown"))
                logger.error(
                    "JOB_HANDLER_ERROR job_id=%s kiosk_id=%s error=%s duration=%.1f pages=%s ts=%s",
                    job_id, kiosk_id, str(exc), duration, pages,
                    datetime.now(tz=UTC).isoformat(),
                )
                await self._report_status(job_id, "FAILED", error=str(exc))
                await self._report_failed(job_id, str(exc))
            finally:
                if pdf_path:
                    await self._downloader.async_cleanup(pdf_path)
                    logger.info(
                        "CLEANUP_COMPLETED job_id=%s kiosk_id=%s path=%s ts=%s",
                        job_id, kiosk_id, pdf_path, datetime.now(tz=UTC).isoformat(),
                    )
                self._active_job_id = None
                self._set_printing(False)

    async def handle_cancel(self, job_id: str) -> None:
        """Cancels an in-progress job."""
        logger.info(
            "JOB_CANCEL_REQUESTED job_id=%s kiosk_id=%s ts=%s",
            job_id, self._settings.kiosk_id, datetime.now(tz=UTC).isoformat(),
        )

    async def _get_download_url(self, job_id: str) -> str:
        """
        Requests a signed download URL via WebSocket.

        Sends DOWNLOAD_URL_REQUEST and waits for a DOWNLOAD_URL message.
        The backend handles generating the signed Supabase URL.

        Raises:
            RuntimeError: If the backend returns DOWNLOAD_URL_ERROR or times out.
        """
        loop = asyncio.get_running_loop()
        future: asyncio.Future[str] = loop.create_future()
        self._pending_download_futures[job_id] = future

        try:
            await self._ws_send({
                "type": "DOWNLOAD_URL_REQUEST",
                "data": {"jobId": job_id},
            })
            logger.info(
                "DOWNLOAD_URL_REQUEST_SENT job_id=%s kiosk_id=%s ts=%s",
                job_id, self._settings.kiosk_id, datetime.now(tz=UTC).isoformat(),
            )
            url = await asyncio.wait_for(future, timeout=30.0)
            logger.info(
                "DOWNLOAD_URL_RESOLVED job_id=%s kiosk_id=%s ts=%s",
                job_id, self._settings.kiosk_id, datetime.now(tz=UTC).isoformat(),
            )
            return url
        finally:
            self._pending_download_futures.pop(job_id, None)

    async def _report_status(self, job_id: str, status: str, error: str | None = None) -> None:
        """
        Reports an intermediate job status to the backend via WebSocket.

        Uses type "JOB_STATUS" — the canonical protocol type expected by the backend.
        """
        payload: dict = {"type": "JOB_STATUS", "data": {"jobId": job_id, "status": status}}
        if error:
            payload["data"]["error"] = error
        try:
            await self._ws_send(payload)
            logger.info(
                "JOB_STATUS_SENT job_id=%s kiosk_id=%s status=%s ts=%s",
                job_id, self._settings.kiosk_id, status, datetime.now(tz=UTC).isoformat(),
            )
        except Exception as exc:
            logger.error(
                "JOB_STATUS_SEND_FAILED job_id=%s kiosk_id=%s status=%s error=%s ts=%s",
                job_id, self._settings.kiosk_id, status, str(exc),
                datetime.now(tz=UTC).isoformat(),
            )

    async def _report_completed(self, job_id: str) -> None:
        """
        Sends a JOB_COMPLETED message to the backend.

        This is distinct from JOB_STATUS(COMPLETED) — it triggers:
        - File deletion from Supabase Storage
        - Final DB record update
        - Prometheus metrics
        """
        try:
            await self._ws_send({"type": "JOB_COMPLETED", "data": {"jobId": job_id}})
            logger.info(
                "JOB_COMPLETED_SENT job_id=%s kiosk_id=%s ts=%s",
                job_id, self._settings.kiosk_id, datetime.now(tz=UTC).isoformat(),
            )
        except Exception as exc:
            logger.error(
                "JOB_COMPLETED_SEND_FAILED job_id=%s kiosk_id=%s error=%s ts=%s",
                job_id, self._settings.kiosk_id, str(exc),
                datetime.now(tz=UTC).isoformat(),
            )

    async def _report_failed(self, job_id: str, reason: str) -> None:
        """
        Sends a JOB_FAILED message to the backend.

        This is distinct from JOB_STATUS(FAILED) — it triggers:
        - Failure reason recorded in DB
        - Prometheus failure counter incremented
        """
        try:
            await self._ws_send({"type": "JOB_FAILED", "data": {"jobId": job_id, "reason": reason}})
            logger.info(
                "JOB_FAILED_SENT job_id=%s kiosk_id=%s reason=%s ts=%s",
                job_id, self._settings.kiosk_id, reason, datetime.now(tz=UTC).isoformat(),
            )
        except Exception as exc:
            logger.error(
                "JOB_FAILED_SEND_FAILED job_id=%s kiosk_id=%s reason=%s error=%s ts=%s",
                job_id, self._settings.kiosk_id, reason, str(exc),
                datetime.now(tz=UTC).isoformat(),
            )

"""
PrintBar Kiosk Agent — Job Handler

Receives JOB_ASSIGNED WebSocket messages, requests a signed download URL via
DOWNLOAD_URL_REQUEST → DOWNLOAD_URL, downloads the PDF, prints it via CUPS,
and reports job status transitions back to the backend.

Every job produces a complete timeline log:
    JOB_ASSIGNED_RECEIVED
    DOWNLOAD_URL_REQUEST_SENT
    DOWNLOAD_URL_RECEIVED
    DOWNLOAD_STARTED
    DOWNLOAD_COMPLETED
    SHA_VERIFIED
    PRINT_STARTED
    CUPS_JOB_CREATED
    PRINT_COMPLETED
    JOB_COMPLETED_SENT  (or JOB_FAILED_SENT)
    TEMP_FILE_REMOVED
    JOB_FINISHED

WebSocket Protocol (Kiosk → Backend):
    JOB_STATUS      — intermediate status update (DOWNLOADING, READY_TO_PRINT, PRINTING)
    JOB_COMPLETED   — job finished successfully (triggers file cleanup on backend)
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


def _now() -> str:
    return datetime.now(tz=UTC).isoformat()


def _ms(start: float, end: float) -> int:
    """Returns elapsed milliseconds between two loop.time() values."""
    return int((end - start) * 1000)


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
                job_id, len(url), _now(),
            )
            fut.set_result(url)
        else:
            logger.warning(
                "DOWNLOAD_URL_RECEIVED_NO_WAITER job_id=%s ts=%s",
                job_id, _now(),
            )

    def reject_download_url(self, job_id: str, error: str) -> None:
        """Called when a DOWNLOAD_URL_ERROR message is received for this job_id."""
        fut = self._pending_download_futures.get(job_id)
        if fut and not fut.done():
            logger.error(
                "DOWNLOAD_URL_ERROR job_id=%s error=%s ts=%s",
                job_id, error, _now(),
            )
            fut.set_exception(RuntimeError(f"Download URL request failed: {error}"))

    async def handle_new_job(self, job_data: dict) -> None:
        """
        Full job lifecycle with complete timeline logging.

        Stages:
            JOB_ASSIGNED_RECEIVED
            → DOWNLOAD_URL_REQUEST_SENT
            → DOWNLOAD_URL_RECEIVED
            → DOWNLOAD_STARTED
            → DOWNLOAD_COMPLETED (+ SHA_VERIFIED)
            → PRINT_STARTED
            → CUPS_JOB_CREATED
            → PRINT_COMPLETED
            → JOB_COMPLETED_SENT / JOB_FAILED_SENT
            → TEMP_FILE_REMOVED
            → JOB_FINISHED

        Args:
            job_data: Payload from the JOB_ASSIGNED WebSocket message.
        """
        job_id = job_data.get("jobId")
        kiosk_id = self._settings.kiosk_id
        t_received = _now()

        if not job_id:
            logger.error("JOB_ASSIGNED_MISSING_JOB_ID ts=%s", t_received)
            return

        logger.info(
            "JOB_ASSIGNED_RECEIVED job_id=%s kiosk_id=%s ts=%s",
            job_id, kiosk_id, t_received,
        )

        async with self._lock:
            if job_id in self._processed_job_ids:
                logger.info(
                    "DUPLICATE_JOB_IGNORED job_id=%s kiosk_id=%s ts=%s",
                    job_id, kiosk_id, _now(),
                )
                return

            self._processed_job_ids.append(job_id)
            if len(self._processed_job_ids) > 200:
                self._processed_job_ids.pop(0)

            self._active_job_id = job_id
            self._set_printing(True)
            pdf_path: str | None = None
            loop = asyncio.get_running_loop()
            t0 = loop.time()

            try:
                # Stage 1: Report DOWNLOADING status.
                await self._report_status(job_id, "DOWNLOADING")

                # Stage 2: Request signed download URL via WebSocket.
                t_url_req = loop.time()
                download_url = await self._get_download_url(job_id)
                t_url_got = loop.time()

                expected_sha256 = job_data.get("sha256")
                expected_size = job_data.get("fileSize")

                # Stage 3: Download PDF.
                t_dl_start = loop.time()
                logger.info(
                    "DOWNLOAD_STARTED job_id=%s kiosk_id=%s url_len=%d ts=%s url_latency_ms=%d",
                    job_id, kiosk_id, len(download_url), _now(), _ms(t_url_req, t_url_got),
                )
                pdf_path = await self._downloader.download(
                    job_id, download_url, expected_sha256, expected_size
                )
                t_dl_done = loop.time()
                logger.info(
                    "DOWNLOAD_COMPLETED job_id=%s kiosk_id=%s path=%s duration_ms=%d ts=%s",
                    job_id, kiosk_id, pdf_path, _ms(t_dl_start, t_dl_done), _now(),
                )

                if expected_sha256:
                    logger.info(
                        "SHA_VERIFIED job_id=%s kiosk_id=%s sha256=%.16s ts=%s",
                        job_id, kiosk_id, expected_sha256, _now(),
                    )

                # Stage 4: Report READY_TO_PRINT, then PRINTING.
                # READY_TO_PRINT is reported to match backend VALID_TRANSITIONS
                # (DOWNLOADING → READY_TO_PRINT → PRINTING).
                await self._report_status(job_id, "READY_TO_PRINT")
                await self._report_status(job_id, "PRINTING")

                copies = job_data.get("copies", 1)
                color_mode = job_data.get("colorMode", "BW")
                duplex = job_data.get("duplex", False)
                paper_size = job_data.get("paperSize", "A4")
                orientation = job_data.get("orientation", "portrait")

                t_print_start = loop.time()
                logger.info(
                    "PRINT_STARTED job_id=%s kiosk_id=%s copies=%s color=%s duplex=%s paper=%s ts=%s",
                    job_id, kiosk_id, copies, color_mode, duplex, paper_size, _now(),
                )

                # Stage 5: Submit to CUPS.
                cups_job_id = self._printer.submit_job(
                    pdf_path,
                    copies=copies,
                    color_mode=color_mode,
                    duplex=duplex,
                    paper_size=paper_size,
                    orientation=orientation,
                )
                t_cups_submitted = loop.time()
                logger.info(
                    "CUPS_JOB_CREATED job_id=%s kiosk_id=%s cups_job_id=%s submit_ms=%d ts=%s",
                    job_id, kiosk_id, cups_job_id, _ms(t_print_start, t_cups_submitted), _now(),
                )

                # Stage 6: Wait for CUPS to finish.
                # Runs in thread pool executor to avoid blocking the asyncio event loop.
                success = await asyncio.get_running_loop().run_in_executor(
                    None,
                    lambda: self._printer.wait_for_completion(
                        cups_job_id, self._settings.print_timeout_sec
                    ),
                )

                t_print_done = loop.time()
                pages = job_data.get("totalPages", job_data.get("pagesSelected", "?"))
                total_ms = _ms(t0, t_print_done)

                if success:
                    logger.info(
                        "PRINT_COMPLETED job_id=%s kiosk_id=%s cups_job_id=%s pages=%s "
                        "print_ms=%d total_ms=%d ts=%s",
                        job_id, kiosk_id, cups_job_id, pages,
                        _ms(t_cups_submitted, t_print_done), total_ms, _now(),
                    )
                    # Stage 7: Notify backend of completion.
                    await self._report_completed(job_id)
                    logger.info(
                        "JOB_COMPLETED_SENT job_id=%s kiosk_id=%s ts=%s",
                        job_id, kiosk_id, _now(),
                    )
                else:
                    logger.error(
                        "PRINT_FAILED job_id=%s kiosk_id=%s cups_job_id=%s pages=%s "
                        "print_ms=%d total_ms=%d ts=%s",
                        job_id, kiosk_id, cups_job_id, pages,
                        _ms(t_cups_submitted, t_print_done), total_ms, _now(),
                    )
                    await self._report_failed(job_id, "CUPS_JOB_INCOMPLETE")
                    logger.info(
                        "JOB_FAILED_SENT job_id=%s kiosk_id=%s ts=%s",
                        job_id, kiosk_id, _now(),
                    )

            except Exception as exc:
                t_err = loop.time()
                logger.error(
                    "JOB_HANDLER_ERROR job_id=%s kiosk_id=%s error=%s total_ms=%d ts=%s",
                    job_id, kiosk_id, str(exc), _ms(t0, t_err), _now(),
                )
                await self._report_failed(job_id, str(exc)[:200])
            finally:
                if pdf_path:
                    try:
                        await self._downloader.async_cleanup(pdf_path)
                        logger.info(
                            "TEMP_FILE_REMOVED job_id=%s kiosk_id=%s path=%s ts=%s",
                            job_id, kiosk_id, pdf_path, _now(),
                        )
                    except Exception as exc:
                        logger.warning(
                            "TEMP_FILE_REMOVE_FAILED job_id=%s error=%s ts=%s",
                            job_id, str(exc), _now(),
                        )
                self._active_job_id = None
                self._set_printing(False)
                logger.info(
                    "JOB_FINISHED job_id=%s kiosk_id=%s total_ms=%d ts=%s",
                    job_id, kiosk_id,
                    _ms(t0, asyncio.get_running_loop().time()), _now(),
                )

    async def handle_cancel(self, job_id: str) -> None:
        """Cancels an in-progress job."""
        logger.info(
            "JOB_CANCEL_REQUESTED job_id=%s kiosk_id=%s ts=%s",
            job_id, self._settings.kiosk_id, _now(),
        )
        # TODO: Cancel CUPS job if cups_job_id is known.

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
                job_id, self._settings.kiosk_id, _now(),
            )
            url = await asyncio.wait_for(future, timeout=30.0)
            logger.info(
                "DOWNLOAD_URL_RESOLVED job_id=%s kiosk_id=%s ts=%s",
                job_id, self._settings.kiosk_id, _now(),
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
                job_id, self._settings.kiosk_id, status, _now(),
            )
        except Exception as exc:
            logger.error(
                "JOB_STATUS_SEND_FAILED job_id=%s kiosk_id=%s status=%s error=%s ts=%s",
                job_id, self._settings.kiosk_id, status, str(exc), _now(),
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
        except Exception as exc:
            logger.error(
                "JOB_COMPLETED_SEND_FAILED job_id=%s kiosk_id=%s error=%s ts=%s",
                job_id, self._settings.kiosk_id, str(exc), _now(),
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
                job_id, self._settings.kiosk_id, reason, _now(),
            )
        except Exception as exc:
            logger.error(
                "JOB_FAILED_SEND_FAILED job_id=%s kiosk_id=%s reason=%s error=%s ts=%s",
                job_id, self._settings.kiosk_id, reason, str(exc), _now(),
            )

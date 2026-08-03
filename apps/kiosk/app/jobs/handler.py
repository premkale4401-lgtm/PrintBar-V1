"""
PrintBar Kiosk Agent — Job Handler

Receives NEW_JOB WebSocket messages, downloads the PDF, prints it via CUPS,
and reports job status transitions back to the backend.
"""
from __future__ import annotations
import asyncio
import logging
import httpx
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

    async def handle_new_job(self, job_data: dict) -> None:
        """
        Full job lifecycle: request download URL → download → verify → print → report.

        Args:
            job_data: Payload from the NEW_JOB WebSocket message.
        """
        job_id = job_data.get("jobId")
        if not job_id:
            logger.error("new_job_missing_job_id")
            return

        async with self._lock:
            if job_id in self._processed_job_ids:
                logger.info("duplicate_job_ignored", job_id=job_id)
                return

            self._processed_job_ids.append(job_id)
            if len(self._processed_job_ids) > 100:
                self._processed_job_ids.pop(0)

            self._active_job_id = job_id
            self._set_printing(True)
            pdf_path: str | None = None
            start_time = asyncio.get_running_loop().time()

            try:
                # 1. Request download URL.
                await self._report_status(job_id, "DOWNLOADING")
                download_url = await self._get_download_url(job_id)
                expected_sha256 = job_data.get("sha256")
                expected_size = job_data.get("fileSize")

                # 2. Download PDF.
                pdf_path = await self._downloader.download(job_id, download_url, expected_sha256, expected_size)

                # 3. Print via CUPS.
                await self._report_status(job_id, "PRINTING")
                cups_job_id = self._printer.submit_job(
                    pdf_path,
                    copies=job_data.get("copies", 1),
                    color_mode=job_data.get("colorMode", "BW"),
                    duplex=job_data.get("duplex", False),
                    paper_size=job_data.get("paperSize", "A4"),
                )

                # 4. Wait for CUPS to finish.
                success = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: self._printer.wait_for_completion(cups_job_id, self._settings.print_timeout_sec),
                )

                duration = asyncio.get_running_loop().time() - start_time
                pages = job_data.get("totalPages", "unknown")

                if success:
                    logger.info("job_completed", job_id=job_id, duration=duration, pages=pages)
                    await self._report_status(job_id, "COMPLETED")
                else:
                    logger.error("job_print_failed", job_id=job_id, duration=duration, pages=pages)
                    await self._report_status(job_id, "FAILED", error="Print job did not complete successfully.")

            except Exception as exc:
                duration = asyncio.get_running_loop().time() - start_time
                pages = job_data.get("totalPages", "unknown")
                logger.error("job_handler_error", job_id=job_id, error=str(exc), duration=duration, pages=pages)
                await self._report_status(job_id, "FAILED", error=str(exc))
            finally:
                if pdf_path:
                    await self._downloader.async_cleanup(pdf_path)
                self._active_job_id = None
                self._set_printing(False)

    async def handle_cancel(self, job_id: str) -> None:
        """Cancels an in-progress job."""
        logger.info("job_cancel_requested", job_id=job_id)
        # CUPS cancellation handled by CupsAdapter if job_id known.

    async def _get_download_url(self, job_id: str) -> str:
        """Requests a signed download URL from the backend."""
        url = f"{self._settings.backend_url}/api/v1/jobs/{job_id}/download-url"
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(url, headers=self._auth_headers_fn())
        resp.raise_for_status()
        return resp.json()["data"]["downloadUrl"]

    async def _report_status(self, job_id: str, status: str, error: str | None = None) -> None:
        """Reports job status to the backend via WebSocket."""
        payload = {"type": "JOB_STATUS_UPDATE", "data": {"jobId": job_id, "status": status}}
        if error:
            payload["data"]["error"] = error
        try:
            await self._ws_send(payload)
        except Exception as exc:
            logger.error("job_status_report_failed", job_id=job_id, status=status, error=str(exc))

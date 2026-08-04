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
        self._pending_download_futures: dict[str, asyncio.Future[str]] = {}

    def resolve_download_url(self, job_id: str, url: str) -> None:
        """Resolves a pending download URL future."""
        fut = self._pending_download_futures.get(job_id)
        if fut and not fut.done():
            fut.set_result(url)

    def reject_download_url(self, job_id: str, error: str) -> None:
        """Rejects a pending download URL future."""
        fut = self._pending_download_futures.get(job_id)
        if fut and not fut.done():
            fut.set_exception(RuntimeError(f"Download URL request failed: {error}"))

    async def handle_new_job(self, job_data: dict) -> None:
        """
        Full job lifecycle: request download URL → download → verify → print → report.

        Args:
            job_data: Payload from the NEW_JOB / JOB_ASSIGNED WebSocket message.
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
                download_url = await self._get_download_url(job_id, job_data)
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
                pages = job_data.get("totalPages", job_data.get("pagesSelected", "unknown"))

                if success:
                    logger.info("job_completed", job_id=job_id, duration=duration, pages=pages)
                    await self._report_status(job_id, "COMPLETED")
                else:
                    logger.error("job_print_failed", job_id=job_id, duration=duration, pages=pages)
                    await self._report_status(job_id, "FAILED", error="Print job did not complete successfully.")

            except Exception as exc:
                duration = asyncio.get_running_loop().time() - start_time
                pages = job_data.get("totalPages", job_data.get("pagesSelected", "unknown"))
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

    async def _get_download_url(self, job_id: str, job_data: dict) -> str:
        """Requests a signed download URL via WS or HTTP."""
        if job_data.get("downloadUrl"):
            return str(job_data["downloadUrl"])
        if job_data.get("url"):
            return str(job_data["url"])

        loop = asyncio.get_running_loop()
        future: asyncio.Future[str] = loop.create_future()
        self._pending_download_futures[job_id] = future

        try:
            await self._ws_send({"type": "DOWNLOAD_URL_REQUEST", "data": {"jobId": job_id}})
            return await asyncio.wait_for(future, timeout=15.0)
        except Exception:
            url = f"{self._settings.backend_url}/api/v1/jobs/{job_id}/download-url"
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(url, headers=self._auth_headers_fn())
            resp.raise_for_status()
            data = resp.json().get("data", {})
            return data.get("downloadUrl") or data.get("url", "")
        finally:
            self._pending_download_futures.pop(job_id, None)

    async def _report_status(self, job_id: str, status: str, error: str | None = None) -> None:
        """Reports job status to the backend via WebSocket."""
        payload = {"type": "JOB_STATUS_UPDATE", "data": {"jobId": job_id, "status": status}}
        if error:
            payload["data"]["error"] = error
        try:
            await self._ws_send(payload)
        except Exception as exc:
            logger.error("job_status_report_failed", job_id=job_id, status=status, error=str(exc))

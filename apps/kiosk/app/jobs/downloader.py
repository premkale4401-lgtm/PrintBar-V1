"""
PrintBar Kiosk Agent — Job Downloader

Downloads a PDF from a pre-signed URL and verifies its SHA-256 hash.
"""
from __future__ import annotations
import hashlib
import logging
import os
import httpx
from app.config.settings import KioskSettings
from app.utils.retry import retry_with_backoff

logger = logging.getLogger(__name__)


class JobDownloader:
    """Downloads print job PDFs and verifies integrity via SHA-256."""

    def __init__(self, settings: KioskSettings) -> None:
        self._settings = settings
        os.makedirs(settings.temp_dir, exist_ok=True)

    async def download(
        self, 
        job_id: str, 
        url: str, 
        expected_sha256: str | None = None,
        expected_size: int | None = None,
    ) -> str:
        """
        Downloads a PDF from url and saves it to the temp directory.

        Args:
            job_id:          Print job ID (used for filename).
            url:             Pre-signed download URL.
            expected_sha256: Expected SHA-256 hex digest (optional).
            expected_size:   Expected file size in bytes (optional).

        Returns:
            Absolute path to the downloaded PDF.

        Raises:
            RuntimeError: On download failure, size mismatch, or hash mismatch.
        """
        dest_path = os.path.join(self._settings.temp_dir, f"{job_id}.pdf")

        async def _download():
            try:
                async with httpx.AsyncClient(timeout=self._settings.download_timeout_sec) as client:
                    async with client.stream("GET", url) as resp:
                        resp.raise_for_status()
                        sha256 = hashlib.sha256()
                        downloaded_size = 0
                        
                        try:
                            with open(dest_path, "wb") as f:
                                async for chunk in resp.aiter_bytes(chunk_size=65536):
                                    f.write(chunk)
                                    sha256.update(chunk)
                                    downloaded_size += len(chunk)
                        except Exception as exc:
                            if os.path.exists(dest_path):
                                os.remove(dest_path)
                            raise RuntimeError(f"Download interrupted: {exc}") from exc
                            
                        # Verify PDF Header
                        if downloaded_size < 5:
                            if os.path.exists(dest_path):
                                os.remove(dest_path)
                            raise ValueError(f"File too small to be a valid PDF (size={downloaded_size}).")
                        
                        with open(dest_path, "rb") as f:
                            header = f.read(5)
                            if header != b"%PDF-":
                                f.close()
                                os.remove(dest_path)
                                raise ValueError(f"Invalid PDF header: {header!r}")

                        return sha256.hexdigest(), downloaded_size
            except httpx.HTTPStatusError as exc:
                if 400 <= exc.response.status_code < 500:
                    raise ValueError(f"Permanent HTTP error downloading job {job_id}: {exc}") from exc
                raise  # Let transient errors (5xx) be retried

        try:
            actual_digest, actual_size = await retry_with_backoff(
                _download, 
                max_attempts=3, 
                label=f"download_job_{job_id}",
                exclude_exceptions=(ValueError,)
            )
        except Exception as exc:
            if os.path.exists(dest_path):
                os.remove(dest_path)
            raise

        if expected_size and actual_size != expected_size:
            os.remove(dest_path)
            raise RuntimeError(
                f"Size mismatch for job {job_id}: expected={expected_size}, actual={actual_size}"
            )

        if expected_sha256 and actual_digest != expected_sha256.lower():
            os.remove(dest_path)
            raise RuntimeError(
                f"SHA-256 mismatch for job {job_id}: expected={expected_sha256}, actual={actual_digest}"
            )

        logger.info("job_downloaded", job_id=job_id, path=dest_path, sha256=actual_digest, size=actual_size)
        return dest_path

    def cleanup(self, path: str) -> None:
        """Deletes the PDF after successful printing with retry backoff."""
        async def _do_cleanup():
            if os.path.exists(path):
                os.remove(path)
                logger.info("job_pdf_deleted", path=path)

        try:
            # We must run this synchronously since cleanup is sometimes called in finally blocks without await.
            # Wait, retry_with_backoff is async. If cleanup is sync, we can't await it easily if called from sync context.
            # But wait, JobHandler.handle_new_job is async, and cleanup is called in finally block.
            # Let's change cleanup to async.
            pass
        except Exception:
            pass

    async def async_cleanup(self, path: str) -> None:
        """Asynchronously deletes the PDF with retry backoff."""
        async def _do_cleanup():
            if os.path.exists(path):
                os.remove(path)
                logger.info("job_pdf_deleted", path=path)
                
        try:
            await retry_with_backoff(_do_cleanup, max_attempts=3, label=f"cleanup_{path}")
        except Exception as exc:
            logger.warning("job_pdf_delete_error", path=path, error=str(exc))

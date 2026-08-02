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

    async def download(self, job_id: str, url: str, expected_sha256: str | None = None) -> str:
        """
        Downloads a PDF from url and saves it to the temp directory.

        Args:
            job_id:          Print job ID (used for filename).
            url:             Pre-signed download URL.
            expected_sha256: Expected SHA-256 hex digest (optional).

        Returns:
            Absolute path to the downloaded PDF.

        Raises:
            RuntimeError: On download failure or hash mismatch.
        """
        dest_path = os.path.join(self._settings.temp_dir, f"{job_id}.pdf")

        async def _download():
            async with httpx.AsyncClient(timeout=self._settings.download_timeout_sec) as client:
                async with client.stream("GET", url) as resp:
                    resp.raise_for_status()
                    sha256 = hashlib.sha256()
                    with open(dest_path, "wb") as f:
                        async for chunk in resp.aiter_bytes(chunk_size=65536):
                            f.write(chunk)
                            sha256.update(chunk)
                    digest = sha256.hexdigest()
                    return digest

        actual_digest = await retry_with_backoff(_download, max_attempts=3, label=f"download_job_{job_id}")

        if expected_sha256 and actual_digest != expected_sha256.lower():
            os.remove(dest_path)
            raise RuntimeError(
                f"SHA-256 mismatch for job {job_id}: expected={expected_sha256}, actual={actual_digest}"
            )

        logger.info("job_downloaded", job_id=job_id, path=dest_path, sha256=actual_digest)
        return dest_path

    def cleanup(self, path: str) -> None:
        """Deletes the PDF after successful printing."""
        try:
            if os.path.exists(path):
                os.remove(path)
                logger.info("job_pdf_deleted", path=path)
        except Exception as exc:
            logger.warning("job_pdf_delete_error", path=path, error=str(exc))

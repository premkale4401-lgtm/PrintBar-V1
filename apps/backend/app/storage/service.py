"""
PrintBar Backend — Supabase Storage Service

Handles all file operations with Supabase Storage:
    - Upload a file object (with exponential-backoff retry)
    - Generate a signed download URL (with retry)
    - Delete a file
    - Verify a file exists

All storage operations use the SERVICE ROLE key (never the anon key).
All buckets must be set to PRIVATE in the Supabase dashboard.

Buckets:
    print-files     — uploaded PDFs awaiting printing
    receipts        — payment receipt PDFs (future)
    reports         — analytics exports (future)
    system-assets   — kiosk configuration files (future)

Retry policy:
    Transient network failures (TimeoutException, ConnectError) are retried
    up to _STORAGE_MAX_RETRIES times with exponential backoff.
    Permanent failures (4xx responses) are NOT retried.
"""

from __future__ import annotations

import asyncio
import hashlib
from typing import BinaryIO  # noqa: F401  — exported for callers

import httpx

from app.core.config import get_settings
from app.core.logging import get_logger
from app.exceptions.base import StorageError

logger = get_logger(__name__)
settings = get_settings()

# Retry configuration for transient storage failures.
_STORAGE_MAX_RETRIES: int = 3
_STORAGE_RETRY_BASE_DELAY: float = 1.0  # seconds — doubles each attempt


class SupabaseStorageService:
    """
    Wraps Supabase Storage REST API for PrintBar file operations.

    Uses httpx async client directly instead of the Supabase Python SDK
    for fine-grained control over timeouts and error handling.

    All methods raise StorageError on failure — never expose raw HTTP errors.
    Transient network errors are automatically retried with exponential backoff.
    """

    def __init__(self) -> None:
        self._base_url = f"{settings.SUPABASE_URL}/storage/v1"
        self._headers = {
            "Authorization": f"Bearer {settings.SUPABASE_SERVICE_ROLE_KEY}",
            "apikey": settings.SUPABASE_SERVICE_ROLE_KEY,
        }

    # ─── Upload ───────────────────────────────────────────────────────────────

    async def upload_file(
        self,
        bucket: str,
        object_path: str,
        file_data: bytes,
        content_type: str = "application/pdf",
    ) -> str:
        """
        Uploads a file to a Supabase Storage bucket.

        Retries up to _STORAGE_MAX_RETRIES times on transient network errors
        with exponential backoff (1s, 2s, 4s).

        Args:
            bucket:       Target bucket name (e.g., "print-files").
            object_path:  Storage path within the bucket (e.g., "2026/08/uuid.pdf").
            file_data:    Raw file bytes.
            content_type: MIME type of the file.

        Returns:
            The full storage path of the uploaded object.

        Raises:
            StorageError: On any upload failure after all retries exhausted.
        """
        url = f"{self._base_url}/object/{bucket}/{object_path}"
        last_error: Exception | None = None

        for attempt in range(1, _STORAGE_MAX_RETRIES + 1):
            try:
                async with httpx.AsyncClient(timeout=60.0) as client:
                    response = await client.post(
                        url,
                        content=file_data,
                        headers={
                            **self._headers,
                            "Content-Type": content_type,
                            "x-upsert": "false",  # Never overwrite existing files.
                        },
                    )

                if response.status_code in (200, 201):
                    logger.info(
                        "storage_upload_success",
                        bucket=bucket,
                        path=object_path,
                        size_bytes=len(file_data),
                        attempt=attempt,
                    )
                    return f"{bucket}/{object_path}"

                # Permanent failures — do not retry 4xx errors.
                if 400 <= response.status_code < 500:
                    logger.error(
                        "storage_upload_permanent_failure",
                        bucket=bucket,
                        path=object_path,
                        status=response.status_code,
                        body=response.text[:200],
                    )
                    raise StorageError(f"Upload rejected: HTTP {response.status_code}")

                # Transient server error — will retry.
                logger.warning(
                    "storage_upload_transient_error",
                    bucket=bucket,
                    path=object_path,
                    status=response.status_code,
                    attempt=attempt,
                )
                last_error = StorageError(f"Upload failed: HTTP {response.status_code}")

            except httpx.TimeoutException as exc:
                logger.warning(
                    "storage_upload_timeout",
                    bucket=bucket,
                    path=object_path,
                    attempt=attempt,
                )
                last_error = exc
            except httpx.ConnectError as exc:
                logger.warning(
                    "storage_upload_connect_error",
                    bucket=bucket,
                    path=object_path,
                    attempt=attempt,
                    error=str(exc),
                )
                last_error = exc
            except httpx.RequestError as exc:
                # Non-retryable network error.
                logger.error("storage_upload_request_error", error=str(exc))
                raise StorageError("Storage service unavailable.") from exc

            if attempt < _STORAGE_MAX_RETRIES:
                delay = _STORAGE_RETRY_BASE_DELAY * (2 ** (attempt - 1))
                logger.info("storage_upload_retrying", delay=delay, attempt=attempt)
                await asyncio.sleep(delay)

        logger.error(
            "storage_upload_all_retries_exhausted",
            bucket=bucket,
            path=object_path,
            retries=_STORAGE_MAX_RETRIES,
        )
        raise StorageError(
            f"File upload failed after {_STORAGE_MAX_RETRIES} attempts. Please try again."
        ) from last_error

    # ─── Signed URLs ──────────────────────────────────────────────────────────

    async def create_signed_url(
        self,
        bucket: str,
        object_path: str,
        expires_in_seconds: int | None = None,
    ) -> str:
        """
        Generates a time-limited signed URL for downloading a private file.

        Used to give the Raspberry Pi kiosk temporary access to a print file.
        Retries on transient network errors.

        Args:
            bucket:             Source bucket.
            object_path:        Path within the bucket.
            expires_in_seconds: URL lifetime. Defaults to settings value.

        Returns:
            Signed URL string valid for the specified duration.

        Raises:
            StorageError: If the signed URL cannot be created after all retries.
        """
        expiry = expires_in_seconds or settings.SIGNED_URL_EXPIRY_SECONDS
        url = f"{self._base_url}/object/sign/{bucket}/{object_path}"
        last_error: Exception | None = None

        for attempt in range(1, _STORAGE_MAX_RETRIES + 1):
            try:
                async with httpx.AsyncClient(timeout=15.0) as client:
                    response = await client.post(
                        url,
                        json={"expiresIn": expiry},
                        headers=self._headers,
                    )

                if response.status_code == 200:
                    data = response.json()
                    signed_url = data.get("signedURL") or data.get("signedUrl")
                    if not signed_url:
                        raise StorageError("Signed URL missing from response.")

                    # Prepend the Supabase URL if it's a relative path.
                    if signed_url.startswith("/"):
                        signed_url = f"{settings.SUPABASE_URL}{signed_url}"

                    return signed_url

                if 400 <= response.status_code < 500:
                    logger.error(
                        "storage_signed_url_permanent_failure",
                        bucket=bucket,
                        path=object_path,
                        status=response.status_code,
                    )
                    raise StorageError("Could not generate download URL.")

                logger.warning(
                    "storage_signed_url_transient_error",
                    bucket=bucket,
                    path=object_path,
                    status=response.status_code,
                    attempt=attempt,
                )
                last_error = StorageError(f"Signed URL failed: HTTP {response.status_code}")

            except httpx.TimeoutException as exc:
                logger.warning("storage_signed_url_timeout", bucket=bucket, attempt=attempt)
                last_error = exc
            except httpx.RequestError as exc:
                logger.error("storage_signed_url_request_error", error=str(exc))
                raise StorageError("Storage service unavailable.") from exc

            if attempt < _STORAGE_MAX_RETRIES:
                delay = _STORAGE_RETRY_BASE_DELAY * (2 ** (attempt - 1))
                await asyncio.sleep(delay)

        raise StorageError(
            f"Could not generate download URL after {_STORAGE_MAX_RETRIES} attempts."
        ) from last_error

    # ─── Delete ───────────────────────────────────────────────────────────────

    async def delete_file(self, bucket: str, object_path: str) -> bool:
        """
        Permanently deletes a file from Supabase Storage.

        Called as part of the post-print cleanup workflow.
        A 404 response is treated as success (idempotent delete).

        Args:
            bucket:       Source bucket.
            object_path:  Path within the bucket.

        Returns:
            True if deleted successfully, False if file was not found.

        Raises:
            StorageError: On unexpected server errors.
        """
        url = f"{self._base_url}/object/{bucket}/{object_path}"

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.delete(url, headers=self._headers)

            if response.status_code == 404:
                logger.warning(
                    "storage_delete_not_found",
                    bucket=bucket,
                    path=object_path,
                )
                return False

            if response.status_code not in (200, 204):
                logger.error(
                    "storage_delete_failed",
                    bucket=bucket,
                    path=object_path,
                    status=response.status_code,
                )
                raise StorageError(f"Delete failed: HTTP {response.status_code}")

        except httpx.RequestError as exc:
            logger.error("storage_delete_request_error", error=str(exc))
            raise StorageError("Storage service unavailable.") from exc

        logger.info("storage_delete_success", bucket=bucket, path=object_path)
        return True

    # ─── File Existence Check ─────────────────────────────────────────────────

    async def file_exists(self, bucket: str, object_path: str) -> bool:
        """
        Checks whether a file exists in Supabase Storage without downloading it.

        Args:
            bucket:       Source bucket.
            object_path:  Path within the bucket.

        Returns:
            True if the file exists, False if not found or on network error.
        """
        url = f"{self._base_url}/object/info/{bucket}/{object_path}"
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url, headers=self._headers)
                return response.status_code == 200
        except httpx.RequestError:
            return False

    # ─── Utilities ────────────────────────────────────────────────────────────

    @staticmethod
    def compute_sha256(data: bytes) -> str:
        """
        Computes the SHA-256 checksum of file bytes.

        Used to verify file integrity before and after download.

        Args:
            data: Raw file bytes.

        Returns:
            Lowercase hex-encoded SHA-256 hash string.
        """
        return hashlib.sha256(data).hexdigest()

    @staticmethod
    def build_object_path(session_id: str, file_id: str) -> str:
        """
        Generates a deterministic, time-partitioned storage path for a file.

        Format: {year}/{month}/{session_id[:8]}/{file_id}.pdf

        This structure:
            - Separates files by month for easy lifecycle management.
            - Groups by session prefix for human readability.
            - Uses the file UUID as the actual filename (collision-proof).

        Args:
            session_id: Guest session ID.
            file_id:    UUID of the UploadedFile record.

        Returns:
            Storage path string (relative to bucket root).
        """
        from datetime import UTC, datetime

        now = datetime.now(tz=UTC)
        return f"{now.year}/{now.month:02d}/{session_id[:8]}/{file_id}.pdf"


class LocalStorageService:
    """
    Local filesystem storage fallback for development.
    Does not require Supabase or external networking.

    IMPORTANT: create_signed_url() returns a full http:// URL using
    settings.BACKEND_BASE_URL so that the Raspberry Pi can download the
    file over the LAN. The backend must mount /local-storage as a static
    file route (done in main.py when SUPABASE_URL is not set).
    """

    def __init__(self) -> None:
        import os

        self.base_dir = os.path.abspath(os.path.join(os.getcwd(), "data", "storage"))
        os.makedirs(self.base_dir, exist_ok=True)
        # Use the backend's own base URL so the Raspberry Pi can resolve it.
        # Trailing slash stripped for consistent URL construction.
        self._backend_base_url = settings.BACKEND_BASE_URL.rstrip("/")

    async def upload_file(
        self,
        bucket: str,
        object_path: str,
        file_data: bytes,
        content_type: str = "application/pdf",
    ) -> str:
        import os

        full_path = os.path.join(self.base_dir, bucket, object_path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)

        try:
            with open(full_path, "wb") as f:
                f.write(file_data)
            logger.info(
                "local_storage_upload_success",
                bucket=bucket,
                path=object_path,
                size_bytes=len(file_data),
            )
            return f"{bucket}/{object_path}"
        except Exception as e:
            logger.error("local_storage_upload_failed", error=str(e))
            raise StorageError(f"Failed to write to local storage: {str(e)}") from e

    async def create_signed_url(
        self,
        bucket: str,
        object_path: str,
        expires_in_seconds: int | None = None,
    ) -> str:
        """
        Returns a fully-qualified HTTP URL for the local file.

        The Raspberry Pi downloads this URL directly from the backend over the LAN.
        The backend must serve /local-storage/* as static files (see main.py).

        Root cause fix: previously returned /local-storage/... (relative path)
        which httpx rejected with "missing http:// or https:// protocol".
        """
        url = f"{self._backend_base_url}/local-storage/{bucket}/{object_path}"
        logger.info(
            "SIGNED_URL_CREATED bucket=%s path=%s url=%s ts=local_storage",
            bucket,
            object_path,
            url,
        )
        return url

    async def delete_file(self, bucket: str, object_path: str) -> bool:
        import os

        full_path = os.path.join(self.base_dir, bucket, object_path)
        if os.path.exists(full_path):
            try:
                os.remove(full_path)
                logger.info("local_storage_delete_success", bucket=bucket, path=object_path)
                return True
            except Exception as e:
                logger.error("local_storage_delete_failed", error=str(e))
                raise StorageError(f"Failed to delete local file: {str(e)}") from e

        logger.warning("local_storage_delete_not_found", bucket=bucket, path=object_path)
        return False

    async def file_exists(self, bucket: str, object_path: str) -> bool:
        import os

        full_path = os.path.join(self.base_dir, bucket, object_path)
        return os.path.exists(full_path)

    @staticmethod
    def compute_sha256(data: bytes) -> str:
        return SupabaseStorageService.compute_sha256(data)

    @staticmethod
    def build_object_path(session_id: str, file_id: str) -> str:
        return SupabaseStorageService.build_object_path(session_id, file_id)


# Module-level singleton — shared across the application lifetime.
storage_service = SupabaseStorageService() if settings.SUPABASE_URL else LocalStorageService()

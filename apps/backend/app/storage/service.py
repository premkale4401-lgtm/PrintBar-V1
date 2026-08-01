"""
PrintBar Backend — Supabase Storage Service

Handles all file operations with Supabase Storage:
    - Upload a file object
    - Generate a signed download URL
    - Delete a file
    - Verify a file exists

All storage operations use the SERVICE ROLE key (never the anon key).
All buckets must be set to PRIVATE in the Supabase dashboard.

Buckets:
    print-files     — uploaded PDFs awaiting printing
    receipts        — payment receipt PDFs (future)
    reports         — analytics exports (future)
    system-assets   — kiosk configuration files (future)
"""

from __future__ import annotations

import hashlib
import io
from typing import BinaryIO

import httpx
import structlog

from app.core.config import get_settings
from app.core.logging import get_logger
from app.exceptions.base import StorageError, StorageObjectNotFoundError

logger = get_logger(__name__)
settings = get_settings()


class StorageService:
    """
    Wraps Supabase Storage REST API for PrintBar file operations.

    Uses httpx async client directly instead of the Supabase Python SDK
    for fine-grained control over timeouts and error handling.

    All methods raise StorageError on failure — never expose raw HTTP errors.
    """

    def __init__(self) -> None:
        self._base_url = f"{settings.SUPABASE_URL}/storage/v1"
        self._headers = {
            "Authorization": f"Bearer {settings.SUPABASE_SERVICE_ROLE_KEY}",
            "apikey": settings.SUPABASE_SERVICE_ROLE_KEY,
        }

    async def upload_file(
        self,
        bucket: str,
        object_path: str,
        file_data: bytes,
        content_type: str = "application/pdf",
    ) -> str:
        """
        Uploads a file to a Supabase Storage bucket.

        Args:
            bucket:       Target bucket name (e.g., "print-files").
            object_path:  Storage path within the bucket (e.g., "2026/08/uuid.pdf").
            file_data:    Raw file bytes.
            content_type: MIME type of the file.

        Returns:
            The full storage path of the uploaded object.

        Raises:
            StorageError: On any upload failure.
        """
        url = f"{self._base_url}/object/{bucket}/{object_path}"

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

                if response.status_code not in (200, 201):
                    logger.error(
                        "storage_upload_failed",
                        bucket=bucket,
                        path=object_path,
                        status=response.status_code,
                        body=response.text[:200],
                    )
                    raise StorageError(f"Upload failed: HTTP {response.status_code}")

        except httpx.TimeoutException:
            logger.error("storage_upload_timeout", bucket=bucket, path=object_path)
            raise StorageError("File upload timed out. Please try again.")
        except httpx.RequestError as exc:
            logger.error("storage_upload_error", error=str(exc))
            raise StorageError("Storage service unavailable.")

        logger.info(
            "storage_upload_success",
            bucket=bucket,
            path=object_path,
            size_bytes=len(file_data),
        )
        return f"{bucket}/{object_path}"

    async def create_signed_url(
        self,
        bucket: str,
        object_path: str,
        expires_in_seconds: int | None = None,
    ) -> str:
        """
        Generates a time-limited signed URL for downloading a private file.

        Used to give the Raspberry Pi kiosk temporary access to a print file.

        Args:
            bucket:             Source bucket.
            object_path:        Path within the bucket.
            expires_in_seconds: URL lifetime. Defaults to settings value.

        Returns:
            Signed URL string valid for the specified duration.

        Raises:
            StorageError: If the signed URL cannot be created.
        """
        expiry = expires_in_seconds or settings.SIGNED_URL_EXPIRY_SECONDS
        url = f"{self._base_url}/object/sign/{bucket}/{object_path}"

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(
                    url,
                    json={"expiresIn": expiry},
                    headers=self._headers,
                )

                if response.status_code != 200:
                    logger.error(
                        "storage_signed_url_failed",
                        bucket=bucket,
                        path=object_path,
                        status=response.status_code,
                    )
                    raise StorageError("Could not generate download URL.")

                data = response.json()
                signed_url = data.get("signedURL") or data.get("signedUrl")
                if not signed_url:
                    raise StorageError("Signed URL missing from response.")

                # Prepend the Supabase URL if it's a relative path.
                if signed_url.startswith("/"):
                    signed_url = f"{settings.SUPABASE_URL}{signed_url}"

                return signed_url

        except httpx.RequestError as exc:
            logger.error("storage_signed_url_error", error=str(exc))
            raise StorageError("Storage service unavailable.")

    async def delete_file(self, bucket: str, object_path: str) -> bool:
        """
        Permanently deletes a file from Supabase Storage.

        Called as part of the post-print cleanup workflow (doc 36).

        Args:
            bucket:       Source bucket.
            object_path:  Path within the bucket.

        Returns:
            True if deleted successfully, False if file not found.

        Raises:
            StorageError: On unexpected errors.
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
            logger.error("storage_delete_error", error=str(exc))
            raise StorageError("Storage service unavailable.")

        logger.info("storage_delete_success", bucket=bucket, path=object_path)
        return True

    async def file_exists(self, bucket: str, object_path: str) -> bool:
        """
        Checks whether a file exists in Supabase Storage without downloading it.

        Args:
            bucket:       Source bucket.
            object_path:  Path within the bucket.

        Returns:
            True if the file exists.
        """
        url = f"{self._base_url}/object/info/{bucket}/{object_path}"
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url, headers=self._headers)
                return response.status_code == 200
        except httpx.RequestError:
            return False

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
        Generates a deterministic storage path for a file.

        Format: {year}/{month}/{session_id[:8]}/{file_id}.pdf

        This structure:
            - Separates files by month for easy lifecycle management.
            - Groups by session prefix for human readability.
            - Uses the file UUID as the actual filename.

        Args:
            session_id: Guest session ID.
            file_id:    UUID of the UploadedFile record.

        Returns:
            Storage path string (relative to bucket root).
        """
        from datetime import UTC, datetime
        now = datetime.now(tz=UTC)
        return f"{now.year}/{now.month:02d}/{session_id[:8]}/{file_id}.pdf"


# Module-level singleton.
storage_service = StorageService()

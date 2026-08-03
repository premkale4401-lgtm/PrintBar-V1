"""
PrintBar Backend — UploadedFile Repository

Data access layer for UploadedFile records.
All database queries for uploaded files go through this class.

Repository Pattern:
    No SQLAlchemy queries exist in services or routes.
    All queries are encapsulated here with typed return values.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.uploaded_file import UploadedFile

logger = get_logger(__name__)


class UploadedFileRepository:
    """
    Repository for UploadedFile CRUD and query operations.

    Args:
        db: SQLAlchemy async session (injected by FastAPI dependency).
    """

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def create(
        self,
        session_id: str,
        storage_path: str,
        storage_bucket: str,
        original_filename: str,
        file_size_bytes: int,
        page_count: int,
        sha256_checksum: str,
        correlation_id: str = "unknown",
        expires_in_minutes: int = 30,
    ) -> UploadedFile:
        """
        Creates a new UploadedFile record after successful storage upload.

        Args:
            session_id:        Guest session ID.
            storage_path:      Path in Supabase Storage.
            storage_bucket:    Bucket name.
            original_filename: Original filename (will be nulled after print).
            file_size_bytes:   File size in bytes.
            page_count:        Number of pages.
            sha256_checksum:   SHA-256 hash of file bytes.
            correlation_id:    Trace ID.
            expires_in_minutes: Minutes until auto-deletion if not paid.

        Returns:
            Newly created UploadedFile instance.
        """
        now = datetime.now(tz=UTC)
        expires_at = (now + timedelta(minutes=expires_in_minutes)).isoformat()

        uploaded_file = UploadedFile(
            session_id=session_id,
            storage_path=storage_path,
            storage_bucket=storage_bucket,
            original_filename=original_filename,
            file_size_bytes=file_size_bytes,
            page_count=page_count,
            sha256_checksum=sha256_checksum,
            is_validated=True,
            is_deleted=False,
            expires_at=expires_at,
            correlation_id=correlation_id,
        )
        self._db.add(uploaded_file)
        await self._db.flush()  # Get the generated ID without committing.

        logger.info(
            "uploaded_file_created",
            file_id=str(uploaded_file.id),
            session_id=session_id,
            page_count=page_count,
            size_bytes=file_size_bytes,
        )
        return uploaded_file

    async def get_by_id(self, file_id: uuid.UUID) -> UploadedFile | None:
        """
        Retrieves an UploadedFile by its UUID.

        Args:
            file_id: UUID of the uploaded file.

        Returns:
            UploadedFile instance or None if not found.
        """
        result = await self._db.execute(
            select(UploadedFile).where(UploadedFile.id == file_id)
        )
        return result.scalar_one_or_none()

    async def get_by_id_and_session(
        self, file_id: uuid.UUID, session_id: str
    ) -> UploadedFile | None:
        """
        Retrieves an UploadedFile only if it belongs to the given session.

        This prevents one session from accessing another session's files.

        Args:
            file_id:    UUID of the uploaded file.
            session_id: Guest session ID.

        Returns:
            UploadedFile instance or None.
        """
        result = await self._db.execute(
            select(UploadedFile).where(
                UploadedFile.id == file_id,
                UploadedFile.session_id == session_id,
                UploadedFile.is_deleted.is_(False),
            )
        )
        return result.scalar_one_or_none()

    async def get_by_sha256_and_session(
        self, sha256_checksum: str, session_id: str
    ) -> UploadedFile | None:
        """
        Retrieves an active UploadedFile by its SHA-256 checksum for a session.
        Used for idempotency to prevent duplicate uploads.

        Args:
            sha256_checksum: SHA-256 hash of the file.
            session_id:      Guest session ID.

        Returns:
            UploadedFile instance or None.
        """
        result = await self._db.execute(
            select(UploadedFile).where(
                UploadedFile.sha256_checksum == sha256_checksum,
                UploadedFile.session_id == session_id,
                UploadedFile.is_deleted.is_(False),
            )
        )
        return result.scalar_one_or_none()

    async def mark_deleted(
        self, file_id: uuid.UUID
    ) -> None:
        """
        Marks a file as deleted per the privacy policy (doc 36).

        Nulls: storage_path, original_filename, sha256_checksum.
        Sets:  is_deleted = True, deleted_at = now.

        The file record is retained for accounting and analytics,
        but all PII and file references are removed.

        Args:
            file_id: UUID of the file to mark deleted.
        """
        now = datetime.now(tz=UTC).isoformat()

        await self._db.execute(
            update(UploadedFile)
            .where(UploadedFile.id == file_id)
            .values(
                storage_path=None,
                original_filename=None,
                sha256_checksum=None,
                is_deleted=True,
                deleted_at=now,
            )
        )
        logger.info("uploaded_file_marked_deleted", file_id=str(file_id))

    async def get_expired_undeleted(self) -> list[UploadedFile]:
        """
        Returns all files that have passed their expiry time but are not yet deleted.

        Used by the cleanup worker to find files eligible for deletion.

        Returns:
            List of UploadedFile records.
        """
        now = datetime.now(tz=UTC).isoformat()
        result = await self._db.execute(
            select(UploadedFile).where(
                UploadedFile.is_deleted.is_(False),
                UploadedFile.expires_at.isnot(None),
                UploadedFile.expires_at <= now,
            )
        )
        return list(result.scalars().all())

"""
PrintBar Backend — Upload Service

Orchestrates the complete file upload workflow:
    1. Validate the PDF (10-step pipeline)
    2. Compute SHA-256 checksum
    3. Upload to Supabase Storage
    4. Create database record
    5. Return response

This service is the single authority for upload business logic.
No validation or storage code lives in the route handler.
"""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.uploaded_file import UploadedFile
from app.repositories.uploaded_file_repository import UploadedFileRepository
from app.storage.service import storage_service
from app.storage.validation import pdf_validator

logger = get_logger(__name__)
settings = get_settings()


class UploadService:
    """
    Orchestrates PDF upload validation, storage, and database registration.

    Args:
        db: Async SQLAlchemy session.
    """

    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._repo = UploadedFileRepository(db)

    async def upload_pdf(
        self,
        session_id: str,
        filename: str,
        content_type: str,
        file_bytes: bytes,
        correlation_id: str = "unknown",
    ) -> UploadedFile:
        """
        Full upload pipeline: validate → checksum → store → persist.

        Args:
            session_id:   Guest session ID from the JWT.
            filename:     Original filename from the multipart upload.
            content_type: MIME type declared by the client.
            file_bytes:   Complete file content.
            correlation_id: Trace ID.

        Returns:
            Persisted UploadedFile database record.
        """
        # Step 1–10: File validation (PDF, JPG, PNG supported).
        page_count = pdf_validator.validate(filename, content_type, file_bytes)

        # Compute SHA-256 for integrity verification at download time.
        sha256 = storage_service.compute_sha256(file_bytes)

        # ── Idempotency Check ─────────────────────────────────────────────────
        existing_file = await self._repo.get_by_sha256_and_session(sha256, session_id)
        if existing_file:
            logger.info(
                "upload_service_idempotent",
                session_id=session_id,
                file_id=str(existing_file.id),
                correlation_id=correlation_id,
            )
            return existing_file

        # Generate a unique file ID for the storage path.
        file_id = str(uuid.uuid4())
        object_path = storage_service.build_object_path(session_id, file_id)
        bucket = settings.STORAGE_BUCKET_PRINT_FILES

        # Determine the correct content type for storage.
        base_mime = content_type.split(";")[0].strip().lower()
        _supported_mimes = {"image/jpeg", "image/jpg", "image/png", "application/pdf"}
        safe_content_type = base_mime if base_mime in _supported_mimes else "application/pdf"

        # Upload to Supabase Storage.
        storage_path = await storage_service.upload_file(
            bucket=bucket,
            object_path=object_path,
            file_data=file_bytes,
            content_type=safe_content_type,
        )

        try:
            # Persist metadata in the database atomically.
            async with self._db.begin_nested():
                uploaded_file = await self._repo.create(
                    session_id=session_id,
                    storage_path=object_path,
                    storage_bucket=bucket,
                    original_filename=filename,
                    file_size_bytes=len(file_bytes),
                    page_count=page_count,
                    sha256_checksum=sha256,
                    correlation_id=correlation_id,
                    expires_in_minutes=settings.ABANDONED_UPLOAD_EXPIRY_MINUTES,
                )

            await self._db.commit()
            logger.info(
                "upload_service_complete",
                session_id=session_id,
                file_id=str(uploaded_file.id),
                page_count=page_count,
                sha256=sha256[:8] + "...",
            )
            return uploaded_file
        except Exception:
            await self._db.rollback()
            # Rollback external storage side-effect if DB fails.
            try:
                await storage_service.delete_file(bucket, object_path)
            except Exception as cleanup_exc:
                logger.error("upload_service_rollback_storage_failed", error=str(cleanup_exc))
            raise

    async def delete_upload(
        self, session_id: str, file_id: uuid.UUID
    ) -> bool:
        """
        Deletes a file from storage and marks the DB record as deleted.

        Only the session that owns the file can delete it.

        Args:
            session_id: Guest session ID.
            file_id:    UUID of the file to delete.

        Returns:
            True if deleted, False if file not found or already deleted.
        """
        uploaded_file = await self._repo.get_by_id_and_session(file_id, session_id)
        if not uploaded_file:
            return False

        try:
            async with self._db.begin_nested():
                await self._repo.mark_deleted(file_id)
            
            # External call inside the overall block, if it fails, the nested block above is rolled back
            if uploaded_file.storage_path:
                await storage_service.delete_file(
                    bucket=uploaded_file.storage_bucket,
                    object_path=uploaded_file.storage_path,
                )
                
            await self._db.commit()
            return True
        except Exception:
            await self._db.rollback()
            raise

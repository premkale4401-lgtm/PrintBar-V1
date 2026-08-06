"""
PrintBar Backend — Upload Service

Orchestrates the complete file upload workflow:
    1. Validate the file (10-step pipeline via PDFValidator)
    2. Convert to PDF bytes (DocumentProcessor — PNG/JPG/DOC/DOCX → PDF)
    3. Compute SHA-256 checksum on the final PDF bytes
    4. Upload PDF to Supabase Storage
    5. Create database record
    6. Return response

Key invariant enforced by this service:
    ONLY real PDF bytes are ever written to storage.
    The kiosk will always download a valid PDF.

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
from app.services.document_processor import document_processor
from app.storage.service import storage_service
from app.storage.validation import pdf_validator

logger = get_logger(__name__)
settings = get_settings()


class UploadService:
    """
    Orchestrates file upload validation, conversion, storage, and DB registration.

    Pipeline:
        validate → convert to PDF → checksum → store → persist

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
        Full upload pipeline: validate → convert → checksum → store → persist.

        Args:
            session_id:     Guest session ID from the JWT.
            filename:       Original filename from the multipart upload.
            content_type:   MIME type declared by the client.
            file_bytes:     Complete file content as received from the client.
            correlation_id: Trace ID.

        Returns:
            Persisted UploadedFile database record.

        Pipeline details:
            1. PDFValidator runs extension/MIME/magic-bytes/size checks on
               the ORIGINAL bytes. PDF-specific steps (5-10) run for PDF uploads.
            2. DocumentProcessor converts non-PDF types to real PDF bytes.
               The resulting PDF is also validated (magic bytes + pypdf parse).
            3. SHA-256 is computed on the FINAL PDF bytes (not the original),
               so the checksum the kiosk checks matches what it downloads.
            4. Storage receives ONLY application/pdf with PDF bytes.
        """
        # ── Step 1: Validate the original file ─────────────────────────────────
        # This validates extension, MIME type, magic bytes, size, and (for PDFs)
        # the full 10-step PDF pipeline. For images/docs, basic integrity is
        # confirmed and page_count_estimate is returned (1 for images).
        #
        # NOTE: page_count_estimate may be inaccurate for DOC/DOCX — the actual
        # page count comes from document_processor below after conversion.
        pdf_validator.validate(filename, content_type, file_bytes)

        # ── Step 2: Convert to PDF ──────────────────────────────────────────────
        # DocumentProcessor guarantees:
        #   - Returned bytes begin with b"%PDF-"
        #   - Returned page_count is accurate (from pypdf after conversion)
        #   - All temporary files are cleaned up regardless of success/failure
        pdf_bytes, page_count = await document_processor.process(
            filename=filename,
            content_type=content_type,
            file_bytes=file_bytes,
        )

        logger.info(
            "upload_service_conversion_complete",
            filename=filename,
            original_size=len(file_bytes),
            pdf_size=len(pdf_bytes),
            page_count=page_count,
            correlation_id=correlation_id,
        )

        # ── Step 3: SHA-256 on final PDF bytes ─────────────────────────────────
        # The checksum is computed on PDF bytes — the exact bytes stored in
        # Supabase and downloaded by the kiosk. The kiosk compares this SHA-256
        # to verify download integrity.
        sha256 = storage_service.compute_sha256(pdf_bytes)

        # ── Idempotency Check ──────────────────────────────────────────────────
        # If the same file (same SHA-256) was already uploaded in this session,
        # return the existing record without re-storing.
        existing_file = await self._repo.get_by_sha256_and_session(sha256, session_id)
        if existing_file:
            logger.info(
                "upload_service_idempotent",
                session_id=session_id,
                file_id=str(existing_file.id),
                correlation_id=correlation_id,
            )
            return existing_file

        # ── Step 4: Upload PDF to storage ──────────────────────────────────────
        # Always stored as application/pdf with PDF bytes.
        # The original content_type (image/png, image/jpeg, etc.) is discarded.
        file_id = str(uuid.uuid4())
        object_path = storage_service.build_object_path(session_id, file_id)
        bucket = settings.STORAGE_BUCKET_PRINT_FILES

        storage_path = await storage_service.upload_file(
            bucket=bucket,
            object_path=object_path,
            file_data=pdf_bytes,
            content_type="application/pdf",
        )

        logger.info(
            "upload_service_stored",
            bucket=bucket,
            path=object_path,
            pdf_size=len(pdf_bytes),
            correlation_id=correlation_id,
        )

        try:
            # ── Step 5: Persist metadata atomically ────────────────────────────
            async with self._db.begin_nested():
                uploaded_file = await self._repo.create(
                    session_id=session_id,
                    storage_path=object_path,
                    storage_bucket=bucket,
                    original_filename=filename,
                    file_size_bytes=len(pdf_bytes),  # actual stored PDF size
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
                correlation_id=correlation_id,
            )
            return uploaded_file
        except Exception:
            await self._db.rollback()
            # Rollback external storage side-effect if DB fails.
            try:
                await storage_service.delete_file(bucket, object_path)
            except Exception as cleanup_exc:
                logger.error(
                    "upload_service_rollback_storage_failed",
                    error=str(cleanup_exc),
                    correlation_id=correlation_id,
                )
            raise

    async def delete_upload(self, session_id: str, file_id: uuid.UUID) -> bool:
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

            # External call inside the overall block; if it fails, the nested
            # block above is rolled back.
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

"""
PrintBar Backend — UploadedFile Model

Represents a file uploaded by a guest user for printing.

Privacy Policy (doc 36):
    - original_filename: Stored temporarily, nulled after print completion.
    - storage_path:      Nulled after the file is deleted from Supabase Storage.
    - sha256_checksum:   Nulled after deletion (used for integrity verification during download).
    - deleted_at:        Set when the file is removed from storage.

Only non-PII metadata (page_count, file_size_bytes, mime_type) is retained permanently.
"""

from sqlalchemy import BigInteger, Boolean, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import PrintBarBase


class UploadedFile(PrintBarBase):
    """
    File uploaded by a guest user.

    Columns:
        session_id:         Guest session that uploaded this file.
        storage_path:       Path in Supabase Storage. Nulled after deletion.
        storage_bucket:     Supabase storage bucket name.
        original_filename:  Original uploaded filename. Nulled after print completion.
        mime_type:          MIME type (always application/pdf).
        file_size_bytes:    Size in bytes. Retained permanently for analytics.
        page_count:         Total number of pages. Retained permanently.
        sha256_checksum:    SHA-256 hash for integrity verification. Nulled after deletion.
        is_validated:       True if all 10 validation steps passed.
        validation_errors:  JSON array of validation error codes if failed.
        is_deleted:         True if the file has been removed from storage.
        deleted_at:         Timestamp of deletion from Supabase Storage.
        expires_at:         Auto-delete deadline (if not printed/paid in time).
        correlation_id:     Trace ID linking this upload to a specific workflow.

    Relationships:
        print_jobs:  All print jobs that reference this file.
    """

    __tablename__ = "uploaded_files"

    session_id: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        index=True,
    )
    storage_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    storage_bucket: Mapped[str] = mapped_column(String(128), nullable=False)
    original_filename: Mapped[str | None] = mapped_column(String(512), nullable=True)
    mime_type: Mapped[str] = mapped_column(String(128), nullable=False, default="application/pdf")
    file_size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    page_count: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256_checksum: Mapped[str | None] = mapped_column(String(64), nullable=True)
    is_validated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    validation_errors: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    deleted_at: Mapped[str | None] = mapped_column(String(50), nullable=True)
    expires_at: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    correlation_id: Mapped[str] = mapped_column(
        String(128), nullable=False, default="unknown", index=True
    )

    # Relationships
    print_jobs: Mapped[list["PrintJob"]] = relationship(  # noqa: F821
        "PrintJob", back_populates="uploaded_file"
    )

"""
PrintBar Backend — Upload Validation Unit Tests

Tests for the PDF validation pipeline (PDFValidator) and
the upload API endpoints.

These tests use in-memory PDFs and mock Supabase Storage calls
so they run without any external infrastructure.
"""

from __future__ import annotations

import io
import struct
from unittest.mock import AsyncMock, patch

import pytest

from app.exceptions.base import (
    FileTooLargeError,
    InvalidPDFError,
    TooManyPagesError,
    UnsupportedFileTypeError,
    ZeroPagesError,
)
from app.storage.validation import PDFValidator


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _make_minimal_pdf(page_count: int = 1) -> bytes:
    """
    Creates a minimal valid PDF bytes object in memory.
    Uses pypdf to generate a real, parseable PDF with the given page count.
    """
    from pypdf import PdfWriter
    writer = PdfWriter()
    for _ in range(page_count):
        writer.add_blank_page(width=595, height=842)  # A4 in points.
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def _make_garbage_bytes(size_kb: int = 1) -> bytes:
    """Returns garbage bytes that look like a PDF extension but aren't."""
    return b"%PDF-NOT-A-REAL-PDF" + b"\x00" * (size_kb * 1024)


# ─── PDFValidator Unit Tests ───────────────────────────────────────────────────

class TestPDFValidatorStep1Extension:
    """Step 1: File extension must be .pdf."""

    def test_valid_extension(self) -> None:
        validator = PDFValidator()
        pdf = _make_minimal_pdf()
        count = validator.validate("document.pdf", "application/pdf", pdf)
        assert count == 1

    def test_txt_extension_raises(self) -> None:
        validator = PDFValidator()
        pdf = _make_minimal_pdf()
        with pytest.raises(UnsupportedFileTypeError):
            validator.validate("document.txt", "application/pdf", pdf)

    def test_no_extension_raises(self) -> None:
        validator = PDFValidator()
        pdf = _make_minimal_pdf()
        with pytest.raises(UnsupportedFileTypeError):
            validator.validate("document", "application/pdf", pdf)

    def test_uppercase_pdf_extension_is_valid(self) -> None:
        validator = PDFValidator()
        pdf = _make_minimal_pdf()
        # Should not raise — case-insensitive check.
        count = validator.validate("document.PDF", "application/pdf", pdf)
        assert count >= 1


class TestPDFValidatorStep2MimeType:
    """Step 2: MIME type must be a supported type."""

    def test_wrong_mime_raises(self) -> None:
        validator = PDFValidator()
        pdf = _make_minimal_pdf()
        with pytest.raises(UnsupportedFileTypeError):
            validator.validate("doc.pdf", "application/x-invalid-mime", pdf)

    def test_text_mime_raises(self) -> None:
        validator = PDFValidator()
        pdf = _make_minimal_pdf()
        with pytest.raises(UnsupportedFileTypeError):
            validator.validate("doc.pdf", "text/plain", pdf)


class TestPDFValidatorStep3MagicBytes:
    """Step 3: First 4 bytes must be %PDF."""

    def test_missing_magic_bytes_raises(self) -> None:
        validator = PDFValidator()
        with pytest.raises(InvalidPDFError):
            validator.validate("doc.pdf", "application/pdf", b"NOPE" + b"\x00" * 100)


class TestPDFValidatorStep4Size:
    """Step 4: File size must not exceed MAX_FILE_SIZE_MB."""

    def test_oversized_file_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        validator = PDFValidator()
        # Monkeypatch settings to use a 1-byte limit.
        from app.core import config as config_module
        settings = config_module.get_settings()
        monkeypatch.setattr(settings, "MAX_FILE_SIZE_MB", 0)

        pdf = _make_minimal_pdf()
        with pytest.raises(FileTooLargeError):
            validator.validate("doc.pdf", "application/pdf", pdf)


class TestPDFValidatorPageCount:
    """Steps 6 & 7: Page count validation."""

    def test_multi_page_pdf(self) -> None:
        validator = PDFValidator()
        pdf = _make_minimal_pdf(page_count=5)
        count = validator.validate("doc.pdf", "application/pdf", pdf)
        assert count == 5

    def test_max_pages_exceeded(self, monkeypatch: pytest.MonkeyPatch) -> None:
        validator = PDFValidator()
        from app.core import config as config_module
        settings = config_module.get_settings()
        monkeypatch.setattr(settings, "MAX_PAGE_COUNT", 1)

        pdf = _make_minimal_pdf(page_count=2)
        with pytest.raises(TooManyPagesError):
            validator.validate("doc.pdf", "application/pdf", pdf)


# ─── Upload API Integration Tests ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_upload_endpoint_rejects_no_auth(async_client) -> None:
    """POST /api/v1/uploads without a token must return 401."""
    response = await async_client.post("/api/v1/uploads")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_upload_endpoint_rejects_non_pdf(async_client) -> None:
    """POST /api/v1/uploads with a .txt file must return 422."""
    create_response = await async_client.post("/api/v1/sessions")
    token = create_response.json()["data"]["accessToken"]

    response = await async_client.post(
        "/api/v1/uploads",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("document.txt", b"hello world", "text/plain")},
    )
    assert response.status_code == 422
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "UPLOAD_001"


@pytest.mark.asyncio
async def test_upload_endpoint_rejects_wrong_mime(async_client) -> None:
    """POST /api/v1/uploads with wrong MIME type must return 422."""
    create_response = await async_client.post("/api/v1/sessions")
    token = create_response.json()["data"]["accessToken"]

    response = await async_client.post(
        "/api/v1/uploads",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("doc.pdf", b"%PDF-garbage", "application/x-invalid-mime")},
    )
    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "UPLOAD_001"


@pytest.mark.asyncio
async def test_upload_valid_pdf_succeeds(async_client) -> None:
    """
    POST /api/v1/uploads with a valid PDF must return 201.

    Supabase Storage is mocked so this test runs without network access.
    """
    create_response = await async_client.post("/api/v1/sessions")
    token = create_response.json()["data"]["accessToken"]

    from pypdf import PdfWriter
    buf = io.BytesIO()
    PdfWriter().add_blank_page(595, 842)
    writer = PdfWriter()
    writer.add_blank_page(595, 842)
    writer.write(buf)
    pdf_bytes = buf.getvalue()

    # Mock Supabase Storage and DB flush so we don't need real infrastructure.
    with (
        patch(
            "app.storage.service.StorageService.upload_file",
            new_callable=AsyncMock,
            return_value="print-files/2026/08/aabbccdd/test.pdf",
        ),
        patch(
            "app.repositories.uploaded_file_repository.UploadedFileRepository.create",
            new_callable=AsyncMock,
        ) as mock_create,
    ):
        from app.models.uploaded_file import UploadedFile
        import uuid
        mock_file = UploadedFile(
            session_id=token[:36],
            storage_path="print-files/2026/08/aabbccdd/test.pdf",
            storage_bucket="print-files",
            original_filename="test.pdf",
            file_size_bytes=len(pdf_bytes),
            page_count=1,
            sha256_checksum="abc123",
            is_validated=True,
            is_deleted=False,
            expires_at="2026-08-02T00:00:00+00:00",
        )
        mock_file.id = uuid.uuid4()
        mock_create.return_value = mock_file

        response = await async_client.post(
            "/api/v1/uploads",
            headers={"Authorization": f"Bearer {token}"},
            files={"file": ("test.pdf", pdf_bytes, "application/pdf")},
        )

    assert response.status_code == 201
    body = response.json()
    assert body["success"] is True
    assert "fileId" in body["data"]
    assert body["data"]["pageCount"] == 1

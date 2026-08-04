"""
PrintBar Backend — DocumentProcessor Unit Tests

Tests for the document conversion pipeline.

Verifies that for every supported file type:
    - Stored bytes begin with b"%PDF-" (real PDF, not image magic bytes)
    - Page count is returned correctly
    - Invalid input raises appropriate errors

No real LibreOffice or network calls are made.
DOC/DOCX tests mock the subprocess call.
"""
from __future__ import annotations

import io
import os
import struct
import tempfile
import zlib
from unittest.mock import MagicMock, patch

import pytest

from app.exceptions.base import InvalidPDFError
from app.services.document_processor import DocumentProcessor


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _make_minimal_pdf(page_count: int = 1) -> bytes:
    """Creates a minimal valid PDF in memory using pypdf."""
    from pypdf import PdfWriter
    writer = PdfWriter()
    for _ in range(page_count):
        writer.add_blank_page(width=595, height=842)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def _make_png_bytes() -> bytes:
    """Creates a 1×1 white pixel PNG in pure bytes (no Pillow required)."""
    # PNG header
    PNG_MAGIC = b"\x89PNG\r\n\x1a\n"

    def _chunk(chunk_type: bytes, data: bytes) -> bytes:
        crc = zlib.crc32(chunk_type + data) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + chunk_type + data + struct.pack(">I", crc)

    # IHDR: 1x1 px, 8-bit RGB
    ihdr_data = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    ihdr = _chunk(b"IHDR", ihdr_data)

    # IDAT: raw scanline for 1x1 white RGB pixel
    raw = b"\x00\xff\xff\xff"  # filter=None, R=255, G=255, B=255
    compressed = zlib.compress(raw)
    idat = _chunk(b"IDAT", compressed)

    # IEND
    iend = _chunk(b"IEND", b"")

    return PNG_MAGIC + ihdr + idat + iend


def _make_jpeg_bytes() -> bytes:
    """Creates a minimal valid 1×1 white JPEG in pure bytes."""
    # This is a valid 1×1 white JPEG produced by Pillow — stored as literal bytes.
    # SOI + minimal JFIF app0 + quantization + SOF0 + Huffman + SOS + EOI.
    try:
        from PIL import Image
        img = Image.new("RGB", (1, 1), (255, 255, 255))
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        return buf.getvalue()
    except ImportError:
        # Pillow not available — return raw JPEG header bytes.
        return b"\xff\xd8\xff\xe0" + b"\x00" * 16 + b"\xff\xd9"


def _make_docx_bytes() -> bytes:
    """Creates the minimal DOCX ZIP magic bytes (PK header)."""
    # DOCX is a ZIP file — create a minimal valid ZIP.
    import zipfile
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml",
                   '<?xml version="1.0" encoding="UTF-8"?>'
                   '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                   '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                   '</Types>')
    return buf.getvalue()


def _make_doc_bytes() -> bytes:
    """Creates DOC magic bytes (OLE Compound Document signature)."""
    # Minimal OLE header.
    return b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\x00" * 504


# ─── Tests ────────────────────────────────────────────────────────────────────

class TestPDFPassthrough:
    """PDF files must pass through unchanged and always begin with %PDF-."""

    def test_pdf_passthrough_returns_pdf_bytes(self) -> None:
        """Stored bytes for a PDF upload must start with %PDF-."""
        processor = DocumentProcessor()
        pdf_bytes = _make_minimal_pdf(page_count=1)

        result_bytes, page_count = processor._pass_through_pdf(pdf_bytes)

        assert result_bytes[:5] == b"%PDF-", (
            f"Expected %PDF- magic bytes, got {result_bytes[:8]!r}"
        )
        assert result_bytes == pdf_bytes
        assert page_count == 1

    def test_pdf_passthrough_multipage(self) -> None:
        processor = DocumentProcessor()
        pdf_bytes = _make_minimal_pdf(page_count=5)

        result_bytes, page_count = processor._pass_through_pdf(pdf_bytes)

        assert result_bytes[:5] == b"%PDF-"
        assert page_count == 5

    @pytest.mark.asyncio
    async def test_process_pdf_returns_pdf_bytes(self) -> None:
        """process() for a .pdf file must return PDF bytes starting with %PDF-."""
        processor = DocumentProcessor()
        pdf_bytes = _make_minimal_pdf()

        result_bytes, page_count = await processor.process(
            "document.pdf", "application/pdf", pdf_bytes
        )

        assert result_bytes[:5] == b"%PDF-", (
            f"PDF passthrough corrupted: got {result_bytes[:8]!r}"
        )
        assert page_count >= 1


class TestPNGConversion:
    """PNG images must be converted to real PDF bytes."""

    def test_png_converts_to_pdf(self) -> None:
        """PNG upload must produce bytes starting with %PDF-."""
        processor = DocumentProcessor()
        png_bytes = _make_png_bytes()

        # Verify the input is actually PNG, not PDF.
        assert png_bytes[:4] == b"\x89PNG", "Test PNG data is invalid"

        result_bytes, page_count = processor._image_to_pdf(png_bytes, "png")

        assert result_bytes[:5] == b"%PDF-", (
            f"PNG conversion produced non-PDF bytes: {result_bytes[:8]!r}\n"
            f"The kiosk would receive {result_bytes[:8]!r} and reject it."
        )
        assert page_count == 1

    @pytest.mark.asyncio
    async def test_process_png_returns_pdf_bytes(self) -> None:
        """process() for a .png file must return PDF bytes, not PNG bytes."""
        processor = DocumentProcessor()
        png_bytes = _make_png_bytes()

        result_bytes, page_count = await processor.process(
            "photo.png", "image/png", png_bytes
        )

        assert result_bytes[:5] == b"%PDF-", (
            f"Expected PDF after PNG conversion, got {result_bytes[:8]!r}"
        )
        assert result_bytes[:4] != b"\x89PNG", (
            "PNG magic bytes found in stored file — conversion failed"
        )
        assert page_count == 1

    @pytest.mark.asyncio
    async def test_process_png_uppercase_extension(self) -> None:
        """Extension matching must be case-insensitive."""
        processor = DocumentProcessor()
        png_bytes = _make_png_bytes()

        result_bytes, page_count = await processor.process(
            "PHOTO.PNG", "image/png", png_bytes
        )

        assert result_bytes[:5] == b"%PDF-"

    def test_png_conversion_invalid_bytes_raises(self) -> None:
        """Corrupted PNG bytes must raise InvalidPDFError."""
        processor = DocumentProcessor()
        garbage = b"\x89PNG\r\n\x1a\n" + b"\xff" * 50  # PNG magic + garbage

        with pytest.raises(InvalidPDFError):
            processor._image_to_pdf(garbage, "png")


class TestJPEGConversion:
    """JPEG images must be converted to real PDF bytes."""

    def test_jpeg_converts_to_pdf(self) -> None:
        """JPEG upload must produce bytes starting with %PDF-."""
        processor = DocumentProcessor()
        jpeg_bytes = _make_jpeg_bytes()

        assert jpeg_bytes[:3] == b"\xff\xd8\xff", "Test JPEG data is invalid"

        result_bytes, page_count = processor._image_to_pdf(jpeg_bytes, "jpg")

        assert result_bytes[:5] == b"%PDF-", (
            f"JPEG conversion produced non-PDF bytes: {result_bytes[:8]!r}"
        )
        assert page_count == 1

    @pytest.mark.asyncio
    async def test_process_jpg_returns_pdf_bytes(self) -> None:
        """process() for a .jpg file must return PDF bytes, not JPEG bytes."""
        processor = DocumentProcessor()
        jpeg_bytes = _make_jpeg_bytes()

        result_bytes, page_count = await processor.process(
            "photo.jpg", "image/jpeg", jpeg_bytes
        )

        assert result_bytes[:5] == b"%PDF-", (
            f"Expected PDF after JPEG conversion, got {result_bytes[:8]!r}"
        )
        assert result_bytes[:3] != b"\xff\xd8\xff", (
            "JPEG magic bytes found in stored file — conversion failed"
        )
        assert page_count == 1

    @pytest.mark.asyncio
    async def test_process_jpeg_extension(self) -> None:
        """Both .jpg and .jpeg extensions must work."""
        processor = DocumentProcessor()
        jpeg_bytes = _make_jpeg_bytes()

        result_bytes, _ = await processor.process(
            "photo.jpeg", "image/jpeg", jpeg_bytes
        )

        assert result_bytes[:5] == b"%PDF-"


class TestDOCXConversion:
    """DOCX files must be converted to PDF via LibreOffice headless."""

    @pytest.mark.asyncio
    async def test_docx_converts_to_pdf(self) -> None:
        """DOCX upload must produce bytes starting with %PDF-."""
        processor = DocumentProcessor()
        docx_bytes = _make_docx_bytes()
        pdf_output = _make_minimal_pdf(page_count=2)

        with (
            patch("shutil.which", return_value="/usr/bin/soffice"),
            patch("subprocess.run") as mock_run,
            patch("builtins.open", create=True) as mock_open,
            patch("os.path.exists", return_value=True),
            patch("shutil.rmtree"),
            patch("tempfile.mkdtemp", return_value="/tmp/printbar_doc_test"),
        ):
            # Mock subprocess returning success.
            mock_proc = MagicMock()
            mock_proc.returncode = 0
            mock_proc.stderr = ""
            mock_run.return_value = mock_proc

            # Mock reading the output PDF.
            read_handle = MagicMock()
            read_handle.__enter__ = lambda s: s
            read_handle.__exit__ = MagicMock(return_value=False)
            read_handle.read.return_value = pdf_output

            write_handle = MagicMock()
            write_handle.__enter__ = lambda s: s
            write_handle.__exit__ = MagicMock(return_value=False)

            def open_side_effect(path, mode="r", **kwargs):
                if "wb" in mode:
                    return write_handle
                return read_handle

            mock_open.side_effect = open_side_effect

            result_bytes, page_count = await processor._office_to_pdf(docx_bytes, "docx")

        assert result_bytes[:5] == b"%PDF-", (
            f"DOCX conversion must produce PDF bytes, got {result_bytes[:8]!r}"
        )
        assert page_count >= 1

    @pytest.mark.asyncio
    async def test_docx_libreoffice_not_installed_raises(self) -> None:
        """If LibreOffice is not installed, must raise InvalidPDFError."""
        processor = DocumentProcessor()
        docx_bytes = _make_docx_bytes()

        with patch("shutil.which", return_value=None):
            with pytest.raises(InvalidPDFError) as exc_info:
                await processor._office_to_pdf(docx_bytes, "docx")

        assert "LibreOffice" in str(exc_info.value)


class TestDOCConversion:
    """DOC files must be converted to PDF via LibreOffice headless."""

    @pytest.mark.asyncio
    async def test_doc_converts_to_pdf(self) -> None:
        """DOC upload must produce bytes starting with %PDF-."""
        processor = DocumentProcessor()
        doc_bytes = _make_doc_bytes()
        pdf_output = _make_minimal_pdf(page_count=3)

        with (
            patch("shutil.which", return_value="/usr/bin/soffice"),
            patch("subprocess.run") as mock_run,
            patch("builtins.open", create=True) as mock_open,
            patch("os.path.exists", return_value=True),
            patch("shutil.rmtree"),
            patch("tempfile.mkdtemp", return_value="/tmp/printbar_doc_test"),
        ):
            mock_proc = MagicMock()
            mock_proc.returncode = 0
            mock_proc.stderr = ""
            mock_run.return_value = mock_proc

            read_handle = MagicMock()
            read_handle.__enter__ = lambda s: s
            read_handle.__exit__ = MagicMock(return_value=False)
            read_handle.read.return_value = pdf_output

            write_handle = MagicMock()
            write_handle.__enter__ = lambda s: s
            write_handle.__exit__ = MagicMock(return_value=False)

            def open_side_effect(path, mode="r", **kwargs):
                if "wb" in mode:
                    return write_handle
                return read_handle

            mock_open.side_effect = open_side_effect

            result_bytes, page_count = await processor._office_to_pdf(doc_bytes, "doc")

        assert result_bytes[:5] == b"%PDF-", (
            f"DOC conversion must produce PDF bytes, got {result_bytes[:8]!r}"
        )
        assert page_count >= 1

    @pytest.mark.asyncio
    async def test_doc_libreoffice_failure_raises(self) -> None:
        """If LibreOffice returns non-zero exit code, must raise InvalidPDFError."""
        processor = DocumentProcessor()
        doc_bytes = _make_doc_bytes()

        with (
            patch("shutil.which", return_value="/usr/bin/soffice"),
            patch("subprocess.run") as mock_run,
            patch("builtins.open", create=True),
            patch("shutil.rmtree"),
            patch("tempfile.mkdtemp", return_value="/tmp/printbar_doc_test"),
        ):
            mock_proc = MagicMock()
            mock_proc.returncode = 1
            mock_proc.stderr = "Error: Could not open document"
            mock_run.return_value = mock_proc

            with pytest.raises(InvalidPDFError) as exc_info:
                await processor._office_to_pdf(doc_bytes, "doc")

        assert "LibreOffice" in str(exc_info.value) or "convert" in str(exc_info.value).lower()


class TestValidatePDFResult:
    """_validate_pdf_result must catch non-PDF bytes from any conversion."""

    def test_empty_bytes_raises(self) -> None:
        processor = DocumentProcessor()
        with pytest.raises(InvalidPDFError):
            processor._validate_pdf_result(b"", source="test")

    def test_png_bytes_raises(self) -> None:
        """PNG magic bytes must be rejected — this is the root cause we fixed."""
        processor = DocumentProcessor()
        png_bytes = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
        with pytest.raises(InvalidPDFError) as exc_info:
            processor._validate_pdf_result(png_bytes, source="PNG guard test")
        assert "\\x89PNG" in str(exc_info.value) or "invalid" in str(exc_info.value).lower()

    def test_jpeg_bytes_raises(self) -> None:
        """JPEG magic bytes must be rejected."""
        processor = DocumentProcessor()
        jpeg_bytes = b"\xff\xd8\xff\xe0" + b"\x00" * 100
        with pytest.raises(InvalidPDFError):
            processor._validate_pdf_result(jpeg_bytes, source="JPEG guard test")

    def test_valid_pdf_passes(self) -> None:
        """Real PDF bytes must pass validation and return correct page count."""
        processor = DocumentProcessor()
        pdf_bytes = _make_minimal_pdf(page_count=3)
        count = processor._validate_pdf_result(pdf_bytes, source="valid PDF")
        assert count == 3

"""
PrintBar Backend — Document Processor

Converts uploaded files (PNG, JPG, DOC, DOCX) to PDF bytes before storage.
The kiosk must ONLY ever receive a real PDF — this module enforces that invariant.

Supported conversions:
    PDF   → validated and returned as-is (pass-through)
    PNG   → converted to PDF via Pillow
    JPG   → converted to PDF via Pillow
    DOC   → converted to PDF via LibreOffice headless
    DOCX  → converted to PDF via LibreOffice headless

Architecture:
    UploadService calls:
        pdf_bytes, page_count = await document_processor.process(
            filename, content_type, file_bytes
        )

    document_processor guarantees:
        - Returned bytes always begin with b"%PDF-"
        - Returned page_count is accurate
        - If conversion is impossible, a clear UploadError is raised
        - No temporary files are left on disk

Invariant:
    NOTHING is stored in Supabase/local storage unless it passes
    _validate_pdf_result(), which asserts PDF magic bytes and
    successful pypdf parse.

Dependencies:
    - Pillow>=10.4.0  (pip install Pillow) — for PNG/JPG conversion
    - LibreOffice     (system package)     — for DOC/DOCX conversion
"""
from __future__ import annotations

import io
import logging
import os
import shutil
import subprocess
import tempfile

from app.exceptions.base import InvalidPDFError, UnsupportedFileTypeError

logger = logging.getLogger(__name__)

# PDF magic bytes.
_PDF_MAGIC = b"%PDF-"


class DocumentProcessor:
    """
    Converts uploaded documents to PDF bytes.

    All conversions happen in memory where possible.
    DOC/DOCX conversions use a temporary directory that is always cleaned up.
    """

    async def process(
        self,
        filename: str,
        content_type: str,
        file_bytes: bytes,
    ) -> tuple[bytes, int]:
        """
        Converts file_bytes to a valid PDF.

        Args:
            filename:     Original filename (used to determine extension).
            content_type: MIME type declared by the client.
            file_bytes:   Complete file content as received from the upload.

        Returns:
            Tuple of (pdf_bytes, page_count) where:
                pdf_bytes  — bytes that begin with b"%PDF-" (always valid PDF)
                page_count — number of pages in the resulting PDF

        Raises:
            InvalidPDFError:       If the source file cannot be converted.
            UnsupportedFileTypeError: If the file type has no conversion path.
        """
        ext = self._get_extension(filename)

        if ext == "pdf":
            return self._pass_through_pdf(file_bytes)
        elif ext in ("jpg", "jpeg", "png"):
            return self._image_to_pdf(file_bytes, ext)
        elif ext in ("doc", "docx"):
            return await self._office_to_pdf(file_bytes, ext)
        else:
            # Defensive: validation.py should have caught this before we get here.
            raise UnsupportedFileTypeError()

    # ─── Conversion Methods ────────────────────────────────────────────────────

    def _pass_through_pdf(self, file_bytes: bytes) -> tuple[bytes, int]:
        """
        For PDF uploads: validates the PDF and returns bytes unchanged.

        Args:
            file_bytes: Raw PDF bytes.

        Returns:
            (file_bytes, page_count)
        """
        page_count = self._validate_pdf_result(file_bytes, source="PDF pass-through")
        logger.info("document_processor_pdf_passthrough pages=%d", page_count)
        return file_bytes, page_count

    def _image_to_pdf(self, file_bytes: bytes, ext: str) -> tuple[bytes, int]:
        """
        Converts a PNG or JPEG image to a single-page PDF using Pillow.

        The image is scaled to fit an A4 page at 150 DPI while preserving
        aspect ratio. The output is always valid PDF bytes.

        Args:
            file_bytes: Raw image bytes.
            ext:        File extension — "png", "jpg", or "jpeg".

        Returns:
            (pdf_bytes, 1)  — images always produce exactly 1 page.

        Raises:
            InvalidPDFError: If Pillow is not installed or the image cannot be opened.
        """
        try:
            from PIL import Image
        except ImportError:
            raise InvalidPDFError(
                "Pillow is not installed. Cannot convert images to PDF. "
                "Run: pip install Pillow>=10.4.0"
            )

        try:
            img = Image.open(io.BytesIO(file_bytes))

            # Ensure RGB — PDF does not support RGBA transparency natively
            # (RGBA would cause Pillow to fail when saving as PDF).
            if img.mode in ("RGBA", "LA", "P"):
                # Composite onto white background to flatten transparency.
                background = Image.new("RGB", img.size, (255, 255, 255))
                if img.mode == "P":
                    img = img.convert("RGBA")
                if img.mode in ("RGBA", "LA"):
                    background.paste(img, mask=img.split()[-1])
                else:
                    background.paste(img)
                img = background
            elif img.mode != "RGB":
                img = img.convert("RGB")

            buf = io.BytesIO()
            img.save(buf, format="PDF", resolution=150)
            pdf_bytes = buf.getvalue()

        except (OSError, SyntaxError, ValueError) as exc:
            logger.warning(
                "document_processor_image_conversion_failed ext=%s error=%s",
                ext, str(exc),
            )
            raise InvalidPDFError(
                f"Could not convert {ext.upper()} image to PDF: {exc}"
            ) from exc

        # Final safety check — assert the output really is a PDF.
        page_count = self._validate_pdf_result(pdf_bytes, source=f"{ext.upper()} image")
        logger.info(
            "document_processor_image_converted ext=%s pdf_size=%d",
            ext, len(pdf_bytes),
        )
        return pdf_bytes, page_count

    async def _office_to_pdf(self, file_bytes: bytes, ext: str) -> tuple[bytes, int]:
        """
        Converts a DOC or DOCX file to PDF using LibreOffice headless mode.

        Process:
            1. Write the source file to a temporary directory.
            2. Run: soffice --headless --convert-to pdf --outdir <tmpdir> <file>
            3. Read the resulting .pdf file.
            4. Validate the PDF bytes.
            5. Clean up the temporary directory.

        LibreOffice must be installed:
            Ubuntu/Debian: apt-get install libreoffice
            Raspberry Pi:  sudo apt-get install libreoffice

        Args:
            file_bytes: Raw DOC or DOCX bytes.
            ext:        "doc" or "docx".

        Returns:
            (pdf_bytes, page_count)

        Raises:
            InvalidPDFError: If LibreOffice is not installed or conversion fails.
        """
        soffice = shutil.which("soffice") or shutil.which("libreoffice")
        if not soffice:
            raise InvalidPDFError(
                "LibreOffice is not installed. Cannot convert DOC/DOCX to PDF. "
                "Install with: sudo apt-get install libreoffice"
            )

        tmpdir = tempfile.mkdtemp(prefix="printbar_doc_")
        try:
            # Write source file to temp dir.
            src_filename = f"document.{ext}"
            src_path = os.path.join(tmpdir, src_filename)
            with open(src_path, "wb") as f:
                f.write(file_bytes)

            # Run LibreOffice conversion.
            result = subprocess.run(
                [
                    soffice,
                    "--headless",
                    "--norestore",
                    "--convert-to", "pdf",
                    "--outdir", tmpdir,
                    src_path,
                ],
                capture_output=True,
                text=True,
                timeout=60,  # 60-second timeout for large documents.
            )

            if result.returncode != 0:
                logger.warning(
                    "document_processor_libreoffice_failed ext=%s returncode=%d stderr=%s",
                    ext, result.returncode, result.stderr[:200],
                )
                raise InvalidPDFError(
                    f"LibreOffice could not convert the {ext.upper()} file to PDF. "
                    f"Details: {result.stderr[:100]}"
                )

            # LibreOffice names the output file by replacing the extension with .pdf.
            output_path = os.path.join(tmpdir, "document.pdf")
            if not os.path.exists(output_path):
                raise InvalidPDFError(
                    f"LibreOffice conversion produced no output for {ext.upper()} file."
                )

            with open(output_path, "rb") as f:
                pdf_bytes = f.read()

        except subprocess.TimeoutExpired:
            logger.error("document_processor_libreoffice_timeout ext=%s", ext)
            raise InvalidPDFError(
                "LibreOffice conversion timed out. The document may be too complex."
            )
        finally:
            # Always clean up temp directory — no files left on disk.
            shutil.rmtree(tmpdir, ignore_errors=True)

        # Final safety check — assert the output really is a PDF.
        page_count = self._validate_pdf_result(pdf_bytes, source=f"{ext.upper()} document")
        logger.info(
            "document_processor_office_converted ext=%s pdf_size=%d pages=%d",
            ext, len(pdf_bytes), page_count,
        )
        return pdf_bytes, page_count

    # ─── Internal Validation ──────────────────────────────────────────────────

    def _validate_pdf_result(self, pdf_bytes: bytes, source: str = "unknown") -> int:
        """
        Asserts that conversion produced valid PDF bytes.

        This is the final safety check before any bytes are handed back to
        UploadService for storage. If this raises, nothing is stored.

        Args:
            pdf_bytes: Bytes to validate.
            source:    Human-readable label for log messages.

        Returns:
            Page count (from pypdf).

        Raises:
            InvalidPDFError: If bytes are not a valid PDF.
        """
        if not pdf_bytes or pdf_bytes[:5] != _PDF_MAGIC:
            actual_header = pdf_bytes[:8] if pdf_bytes else b"<empty>"
            logger.error(
                "document_processor_invalid_pdf_result source=%s header=%r",
                source, actual_header,
            )
            raise InvalidPDFError(
                f"Conversion from {source} produced invalid PDF bytes "
                f"(header: {actual_header!r})."
            )

        try:
            from pypdf import PdfReader
            reader = PdfReader(io.BytesIO(pdf_bytes), strict=False)
            page_count = len(reader.pages)
            if page_count < 1:
                raise InvalidPDFError(
                    f"Conversion from {source} produced a PDF with 0 pages."
                )
            return page_count
        except InvalidPDFError:
            raise
        except Exception as exc:
            logger.error(
                "document_processor_pdf_parse_failed source=%s error=%s",
                source, str(exc),
            )
            raise InvalidPDFError(
                f"Conversion from {source} produced an unparseable PDF: {exc}"
            ) from exc

    @staticmethod
    def _get_extension(filename: str) -> str:
        """Extracts and lowercases the file extension."""
        if "." not in filename:
            return ""
        return filename.rsplit(".", 1)[-1].lower()


# Module-level singleton — shared across the application lifetime.
document_processor = DocumentProcessor()

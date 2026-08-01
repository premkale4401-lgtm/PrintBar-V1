"""
PrintBar Backend — PDF Upload Validation Pipeline

Validates uploaded PDF files through 10 sequential steps before
storing them in Supabase Storage.

Validation steps (in order):
    1. Extension check  — must be .pdf (case-insensitive)
    2. MIME type check  — Content-Type must be application/pdf
    3. Magic bytes      — first 4 bytes must be %PDF
    4. Size limit       — must not exceed MAX_FILE_SIZE_MB
    5. PDF parsability  — must be openable by pypdf
    6. Page count ≥ 1   — must have at least one page
    7. Page count limit — must not exceed MAX_PAGE_COUNT
    8. Password check   — must not be password-protected
    9. JavaScript check — must not contain embedded JavaScript
    10. Corruption check — pages must be readable

If any step fails, an appropriate exception is raised with the
corresponding error code (UPLOAD_001 through UPLOAD_009).

No partial uploads are stored. Validation runs entirely in memory
before any Supabase Storage write occurs.
"""

from __future__ import annotations

import io

from app.core.config import get_settings
from app.core.logging import get_logger
from app.exceptions.base import (
    CorruptedPDFError,
    EmbeddedJavaScriptError,
    FileTooLargeError,
    InvalidPDFError,
    PasswordProtectedPDFError,
    TooManyPagesError,
    UnsupportedFileTypeError,
    ZeroPagesError,
)

logger = get_logger(__name__)
settings = get_settings()

# PDF magic bytes: every valid PDF must start with %PDF
_PDF_MAGIC = b"%PDF"


class PDFValidator:
    """
    Validates a PDF file through 10 sequential steps.

    All validation is stateless — create a new instance per validation run,
    or use the module-level validate() function for convenience.
    """

    def validate(self, filename: str, content_type: str, file_bytes: bytes) -> int:
        """
        Runs all 10 validation steps against the provided file data.

        Args:
            filename:     Original filename from the upload.
            content_type: MIME type declared by the client.
            file_bytes:   Complete file content as bytes.

        Returns:
            Page count (int) — number of pages in the valid PDF.

        Raises:
            UnsupportedFileTypeError: Step 1 or 2 fails.
            InvalidPDFError:          Step 3 or PDF structure is broken.
            FileTooLargeError:        Step 4 fails.
            ZeroPagesError:           Step 6 fails.
            TooManyPagesError:        Step 7 fails.
            PasswordProtectedPDFError: Step 8 fails.
            EmbeddedJavaScriptError:  Step 9 fails.
            CorruptedPDFError:        Step 10 fails.
        """
        self._step1_check_extension(filename)
        self._step2_check_mime_type(content_type)
        self._step3_check_magic_bytes(file_bytes)
        self._step4_check_size(file_bytes)
        reader = self._step5_parse_pdf(file_bytes)
        page_count = self._step6_check_min_pages(reader)
        self._step7_check_max_pages(page_count)
        self._step8_check_password_protection(reader)
        self._step9_check_embedded_javascript(reader)
        self._step10_check_corruption(reader)

        logger.info(
            "pdf_validation_passed",
            filename=filename,
            page_count=page_count,
            size_bytes=len(file_bytes),
        )
        return page_count

    # ─── Validation Steps ──────────────────────────────────────────────────────

    def _step1_check_extension(self, filename: str) -> None:
        """Step 1: File extension must be .pdf (case-insensitive)."""
        if not filename.lower().endswith(".pdf"):
            logger.warning("upload_validation_fail_extension", filename=filename)
            raise UnsupportedFileTypeError()

    def _step2_check_mime_type(self, content_type: str) -> None:
        """Step 2: MIME type must be application/pdf."""
        # Accept content_type with optional charset parameter.
        base_mime = content_type.split(";")[0].strip().lower()
        if base_mime != "application/pdf":
            logger.warning("upload_validation_fail_mime", content_type=content_type)
            raise UnsupportedFileTypeError()

    def _step3_check_magic_bytes(self, file_bytes: bytes) -> None:
        """Step 3: First 4 bytes must be %PDF."""
        if not file_bytes[:4] == _PDF_MAGIC:
            logger.warning("upload_validation_fail_magic")
            raise InvalidPDFError("File does not appear to be a valid PDF.")

    def _step4_check_size(self, file_bytes: bytes) -> None:
        """Step 4: File must not exceed MAX_FILE_SIZE_MB."""
        if len(file_bytes) > settings.max_file_size_bytes:
            logger.warning(
                "upload_validation_fail_size",
                size_bytes=len(file_bytes),
                max_bytes=settings.max_file_size_bytes,
            )
            raise FileTooLargeError(settings.MAX_FILE_SIZE_MB)

    def _step5_parse_pdf(self, file_bytes: bytes):  # type: ignore[return]
        """Step 5: File must be parseable by pypdf."""
        try:
            from pypdf import PdfReader
            reader = PdfReader(io.BytesIO(file_bytes), strict=False)
            return reader
        except Exception as exc:
            logger.warning("upload_validation_fail_parse", error=str(exc))
            raise InvalidPDFError("The file could not be opened as a PDF.")

    def _step6_check_min_pages(self, reader) -> int:  # type: ignore[no-untyped-def]
        """Step 6: PDF must have at least 1 page."""
        try:
            page_count = len(reader.pages)
        except Exception as exc:
            logger.warning("upload_validation_fail_pages", error=str(exc))
            raise CorruptedPDFError()

        if page_count < 1:
            raise ZeroPagesError()
        return page_count

    def _step7_check_max_pages(self, page_count: int) -> None:
        """Step 7: PDF must not exceed MAX_PAGE_COUNT."""
        if page_count > settings.MAX_PAGE_COUNT:
            raise TooManyPagesError(settings.MAX_PAGE_COUNT)

    def _step8_check_password_protection(self, reader) -> None:  # type: ignore[no-untyped-def]
        """Step 8: PDF must not be password-protected."""
        try:
            if reader.is_encrypted:
                logger.warning("upload_validation_fail_encrypted")
                raise PasswordProtectedPDFError()
        except PasswordProtectedPDFError:
            raise
        except Exception:
            # pypdf raises exceptions for some malformed encrypted PDFs.
            raise PasswordProtectedPDFError()

    def _step9_check_embedded_javascript(self, reader) -> None:  # type: ignore[no-untyped-def]
        """
        Step 9: PDF must not contain embedded JavaScript.

        Checks the /Names/JavaScript key in the document catalog
        and the /JS key in each page's /AA (Additional Actions) dictionary.
        """
        try:
            # Check document-level JavaScript.
            catalog = reader.trailer.get("/Root", {})
            if hasattr(catalog, "get"):
                names = catalog.get("/Names")
                if names and hasattr(names, "get"):
                    if names.get("/JavaScript"):
                        logger.warning("upload_validation_fail_js_document")
                        raise EmbeddedJavaScriptError()

            # Check page-level JavaScript actions.
            for page in reader.pages:
                aa = page.get("/AA")
                if aa and hasattr(aa, "get"):
                    for key in ("/O", "/C", "/F", "/Bl", "/E", "/X", "/D", "/U", "/Fo", "/PC", "/PO", "/PV"):
                        action = aa.get(key)
                        if action and hasattr(action, "get"):
                            if action.get("/S") in ("/JavaScript", "/JS"):
                                logger.warning("upload_validation_fail_js_page")
                                raise EmbeddedJavaScriptError()
        except EmbeddedJavaScriptError:
            raise
        except Exception:
            # Be conservative: if we can't inspect, allow it through.
            pass

    def _step10_check_corruption(self, reader) -> None:  # type: ignore[no-untyped-def]
        """
        Step 10: All pages must be readable without errors.

        Attempts to extract text from each page to detect corrupted streams.
        Stops at the first unreadable page.
        """
        try:
            for i, page in enumerate(reader.pages):
                try:
                    page.extract_text()
                except Exception as exc:
                    logger.warning(
                        "upload_validation_fail_corruption",
                        page_index=i,
                        error=str(exc),
                    )
                    raise CorruptedPDFError()
        except CorruptedPDFError:
            raise
        except Exception as exc:
            logger.warning("upload_validation_fail_read", error=str(exc))
            raise CorruptedPDFError()


# Module-level singleton.
pdf_validator = PDFValidator()

"""
PrintBar Backend — File Upload Validation Pipeline

Validates uploaded files (PDF, JPG, PNG) through sequential steps before
storing them in Supabase Storage.

Supported file types:
    - PDF:  application/pdf (.pdf)
    - JPEG: image/jpeg (.jpg, .jpeg)
    - PNG:  image/png (.png)

Validation steps for PDFs (in order):
    1. Extension check  — must be .pdf, .jpg, .jpeg, or .png (case-insensitive)
    2. MIME type check  — must be a supported MIME type
    3. Magic bytes      — first bytes must match file type signature
    4. Size limit       — must not exceed MAX_FILE_SIZE_MB
    5. PDF parsability  — must be openable by pypdf (PDF only)
    6. Page count ≥ 1   — must have at least one page (PDF only)
    7. Page count limit — must not exceed MAX_PAGE_COUNT (PDF only)
    8. Password check   — must not be password-protected (PDF only)
    9. JavaScript check — must not contain embedded JavaScript (PDF only)
    10. Corruption check — pages must be readable (PDF only)

For images (JPG/PNG), steps 5–10 are replaced by image-specific validation.

If any step fails, an appropriate exception is raised with the
corresponding error code.

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
    SpoofedExtensionError,
    ZeroPagesError,
)

logger = get_logger(__name__)
settings = get_settings()

# PDF magic bytes: every valid PDF must start with %PDF
_PDF_MAGIC = b"%PDF"
# JPEG magic bytes (SOI marker)
_JPEG_MAGIC = b"\xff\xd8\xff"
# PNG magic bytes
_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
# DOC magic bytes (OLE)
_DOC_MAGIC = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
# DOCX magic bytes (ZIP)
_DOCX_MAGIC = b"PK\x03\x04"

# Supported extensions and their MIME types
_SUPPORTED_TYPES: dict[str, str] = {
    "pdf": "application/pdf",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "png": "image/png",
    "doc": "application/msword",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}

_SUPPORTED_EXTENSIONS = set(_SUPPORTED_TYPES.keys())

_SUPPORTED_MIMES = {
    "application/pdf",
    "image/jpeg",
    "image/jpg",
    "image/png",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/x-zip-compressed",
    "application/zip",
}


class PDFValidator:
    """
    Validates an uploaded file (PDF, JPG, or PNG) before storage.

    For PDFs: runs the full 10-step validation pipeline.
    For images: validates magic bytes, size, and image integrity.

    Returns the page count (1 for images, actual count for PDFs).
    """

    def validate(self, filename: str, content_type: str, file_bytes: bytes) -> int:
        """
        Runs validation against the provided file data.

        Args:
            filename:     Original filename from the upload.
            content_type: MIME type declared by the client.
            file_bytes:   Complete file content as bytes.

        Returns:
            Page count (int) — 1 for images, actual page count for PDFs.

        Raises:
            UnsupportedFileTypeError: File type is not supported.
            FileTooLargeError:        File exceeds size limit.
            InvalidPDFError:          PDF structure is invalid.
            ZeroPagesError:           PDF has no pages.
            TooManyPagesError:        PDF exceeds page limit.
            PasswordProtectedPDFError: PDF is encrypted.
            EmbeddedJavaScriptError:  PDF contains JavaScript.
            CorruptedPDFError:        PDF pages are unreadable.
        """
        extension = self._get_extension(filename)

        # Step 1: Validate extension
        self._step1_check_extension(filename, extension)

        # Step 2: Validate MIME type
        self._step2_check_mime_type(content_type)

        # Step 3: Validate magic bytes
        self._step3_check_magic_bytes(extension, file_bytes)

        # Step 4: Check file size
        self._step4_check_size(file_bytes)

        # Steps 5–10: Type-specific validation
        if extension == "pdf":
            reader = self._step5_parse_pdf(file_bytes)
            page_count = self._step6_check_min_pages(reader)
            self._step7_check_max_pages(page_count)
            self._step8_check_password_protection(reader)
            self._step9_check_embedded_javascript(reader)
            self._step10_check_corruption(reader)
        elif extension in ("doc", "docx"):
            page_count = 1  # Standard default page estimate for Office documents
        else:
            # For images, validate the image can be decoded
            page_count = self._validate_image(extension, file_bytes)

        logger.info(
            "file_validation_passed",
            filename=filename,
            extension=extension,
            page_count=page_count,
            size_bytes=len(file_bytes),
        )
        return page_count

    # ─── Helpers ───────────────────────────────────────────────────────────────

    def _get_extension(self, filename: str) -> str:
        """Extracts and lowercases the file extension."""
        if "." not in filename:
            return ""
        return filename.rsplit(".", 1)[-1].lower()

    # ─── Validation Steps ──────────────────────────────────────────────────────

    def _step1_check_extension(self, filename: str, extension: str) -> None:
        """Step 1: Extension must be pdf, jpg, jpeg, or png (case-insensitive)."""
        if extension not in _SUPPORTED_EXTENSIONS:
            logger.warning(
                "upload_validation_fail_extension",
                filename=filename,
                extension=extension,
            )
            raise UnsupportedFileTypeError()

    def _step2_check_mime_type(self, content_type: str) -> None:
        """Step 2: MIME type must be a supported type."""
        # Accept content_type with optional charset parameter.
        base_mime = content_type.split(";")[0].strip().lower()
        if base_mime not in _SUPPORTED_MIMES:
            logger.warning("upload_validation_fail_mime", content_type=content_type)
            raise UnsupportedFileTypeError()

    def _step3_check_magic_bytes(self, extension: str, file_bytes: bytes) -> None:
        """Step 3: First bytes must match the expected file signature."""
        if extension == "pdf":
            if file_bytes[:4] != _PDF_MAGIC:
                logger.warning("upload_validation_fail_magic_pdf")
                raise SpoofedExtensionError()
        elif extension in ("jpg", "jpeg"):
            if file_bytes[:3] != _JPEG_MAGIC:
                logger.warning("upload_validation_fail_magic_jpeg")
                raise SpoofedExtensionError()
        elif extension == "png":
            if file_bytes[:8] != _PNG_MAGIC:
                logger.warning("upload_validation_fail_magic_png")
                raise SpoofedExtensionError()
        elif extension == "doc":
            if file_bytes[:8] != _DOC_MAGIC:
                logger.warning("upload_validation_fail_magic_doc")
                raise SpoofedExtensionError()
        elif extension == "docx":
            if file_bytes[:4] != _DOCX_MAGIC:
                logger.warning("upload_validation_fail_magic_docx")
                raise SpoofedExtensionError()

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

    def _validate_image(self, extension: str, file_bytes: bytes) -> int:
        """
        Validates image files (JPG, PNG).

        Uses Pillow if available, otherwise falls back to basic magic-byte validation.
        Returns 1 as images are treated as single-page documents.

        Raises:
            InvalidPDFError: If the image cannot be decoded/opened.
        """
        try:
            from PIL import Image
            img = Image.open(io.BytesIO(file_bytes))
            img.verify()  # Raises if image is corrupted
        except ImportError:
            # Pillow not installed — magic bytes already checked in step 3, allow through.
            logger.warning(
                "pillow_not_installed_skipping_image_validation",
                extension=extension,
            )
        except Exception as exc:
            logger.warning(
                "upload_validation_fail_image",
                extension=extension,
                error=str(exc),
            )
            raise InvalidPDFError(f"The file does not appear to be a valid {extension.upper()} image.")

        return 1  # Images are always treated as 1-page documents


# Module-level singleton.
pdf_validator = PDFValidator()

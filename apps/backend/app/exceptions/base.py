"""
PrintBar Backend — Custom Exception Hierarchy

All application-specific errors subclass PrintBarError.
Every exception maps to a standardized API error code and HTTP status code.

HTTP errors are never exposed with raw stack traces.
Internal error details are logged; clients receive only the error code and message.
"""

from http import HTTPStatus


class PrintBarError(Exception):
    """
    Base exception for all PrintBar application errors.

    Args:
        message: Human-readable error message (safe to send to clients).
        error_code: Structured error code from constants (e.g., "UPLOAD_001").
        status_code: HTTP status code for the response.
    """

    def __init__(
        self,
        message: str,
        error_code: str = "SYS_000",
        status_code: int = HTTPStatus.INTERNAL_SERVER_ERROR,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.status_code = status_code


# ─── Authentication & Authorization ───────────────────────────────────────────

class AuthenticationError(PrintBarError):
    """Raised when authentication credentials are missing or invalid."""

    def __init__(self, message: str = "Authentication failed.", error_code: str = "AUTH_001") -> None:
        super().__init__(message, error_code, HTTPStatus.UNAUTHORIZED)


class AuthorizationError(PrintBarError):
    """Raised when the authenticated identity lacks permission for an action."""

    def __init__(self, message: str = "Permission denied.", error_code: str = "AUTH_004") -> None:
        super().__init__(message, error_code, HTTPStatus.FORBIDDEN)


class TokenExpiredError(AuthenticationError):
    """Raised when a JWT token has expired."""

    def __init__(self) -> None:
        super().__init__("Token has expired.", "AUTH_002")


class InvalidCredentialsError(AuthenticationError):
    """Raised when login credentials are incorrect."""

    def __init__(self) -> None:
        super().__init__("Invalid credentials.", "AUTH_003")


# ─── Upload & File Handling ────────────────────────────────────────────────────

class UploadError(PrintBarError):
    """Base class for all upload-related errors."""

    def __init__(self, message: str, error_code: str = "UPLOAD_000") -> None:
        super().__init__(message, error_code, HTTPStatus.UNPROCESSABLE_ENTITY)


class UnsupportedFileTypeError(UploadError):
    def __init__(self) -> None:
        super().__init__("Unsupported file type. Please upload a PDF, JPG, or PNG file.", "UPLOAD_001")


class FileTooLargeError(UploadError):
    def __init__(self, max_mb: int) -> None:
        super().__init__(f"File exceeds the {max_mb} MB limit.", "UPLOAD_002")


class InvalidPDFError(UploadError):
    def __init__(self, reason: str = "The file is not a valid PDF.") -> None:
        super().__init__(reason, "UPLOAD_003")


class PasswordProtectedPDFError(UploadError):
    def __init__(self) -> None:
        super().__init__("Password-protected PDFs cannot be printed.", "UPLOAD_004")


class EmbeddedJavaScriptError(UploadError):
    def __init__(self) -> None:
        super().__init__("PDFs containing embedded JavaScript are not allowed.", "UPLOAD_005")


class EmbeddedFilesError(UploadError):
    def __init__(self) -> None:
        super().__init__("PDFs with embedded files are not allowed.", "UPLOAD_006")


class ZeroPagesError(UploadError):
    def __init__(self) -> None:
        super().__init__("The PDF contains no printable pages.", "UPLOAD_007")


class CorruptedPDFError(UploadError):
    def __init__(self) -> None:
        super().__init__("The PDF file appears to be corrupted.", "UPLOAD_008")


class TooManyPagesError(UploadError):
    def __init__(self, max_pages: int) -> None:
        super().__init__(f"PDFs may not exceed {max_pages} pages.", "UPLOAD_009")


class UploadNotFoundError(PrintBarError):
    def __init__(self) -> None:
        super().__init__("Upload not found.", "UPLOAD_010", HTTPStatus.NOT_FOUND)


# ─── Payment ───────────────────────────────────────────────────────────────────

class PaymentError(PrintBarError):
    """Base class for payment-related errors."""

    def __init__(self, message: str, error_code: str = "PAY_000") -> None:
        super().__init__(message, error_code, HTTPStatus.BAD_REQUEST)


class InvalidPaymentSignatureError(PaymentError):
    def __init__(self) -> None:
        super().__init__("Payment signature verification failed.", "PAY_001")


class PaymentTimeoutError(PaymentError):
    def __init__(self) -> None:
        super().__init__("Payment has expired.", "PAY_002")


class PaymentAmountMismatchError(PaymentError):
    def __init__(self) -> None:
        super().__init__("Payment amount does not match the order.", "PAY_003")


class DuplicatePaymentError(PaymentError):
    def __init__(self) -> None:
        super().__init__("This payment has already been processed.", "PAY_004")


class PaymentGatewayError(PaymentError):
    def __init__(self) -> None:
        super().__init__("A payment gateway error occurred. Please try again.", "PAY_005")


class PaymentOrderNotFoundError(PaymentError):
    def __init__(self) -> None:
        super().__init__("Payment order not found.", "PAY_006", )


class CurrencyMismatchError(PaymentError):
    def __init__(self) -> None:
        super().__init__("Payment currency does not match the order.", "PAY_007")


# ─── Print Job ─────────────────────────────────────────────────────────────────

class JobNotFoundError(PrintBarError):
    def __init__(self) -> None:
        super().__init__("Print job not found.", "JOB_001", HTTPStatus.NOT_FOUND)


class InvalidJobTransitionError(PrintBarError):
    def __init__(self, current: str, target: str) -> None:
        super().__init__(
            f"Cannot transition job from {current} to {target}.",
            "JOB_002",
            HTTPStatus.CONFLICT,
        )


class NoKioskAvailableError(PrintBarError):
    def __init__(self) -> None:
        super().__init__(
            "No kiosk is currently available to handle this job.",
            "JOB_003",
            HTTPStatus.SERVICE_UNAVAILABLE,
        )


# ─── Kiosk ─────────────────────────────────────────────────────────────────────

class KioskNotRegisteredError(PrintBarError):
    def __init__(self) -> None:
        super().__init__("Kiosk is not registered.", "KIOSK_001", HTTPStatus.UNAUTHORIZED)


class KioskOfflineError(PrintBarError):
    def __init__(self) -> None:
        super().__init__("Kiosk is offline.", "KIOSK_002", HTTPStatus.SERVICE_UNAVAILABLE)


class KioskInvalidApiKeyError(PrintBarError):
    def __init__(self) -> None:
        super().__init__("Invalid kiosk API key.", "KIOSK_003", HTTPStatus.UNAUTHORIZED)


# ─── Storage ───────────────────────────────────────────────────────────────────

class StorageError(PrintBarError):
    """Raised on Supabase Storage operation failures."""

    def __init__(self, message: str = "A storage error occurred.") -> None:
        super().__init__(message, "STORAGE_001", HTTPStatus.INTERNAL_SERVER_ERROR)


class StorageObjectNotFoundError(PrintBarError):
    def __init__(self) -> None:
        super().__init__("Storage object not found.", "STORAGE_002", HTTPStatus.NOT_FOUND)


# ─── Session ───────────────────────────────────────────────────────────────────

class SessionExpiredError(PrintBarError):
    def __init__(self) -> None:
        super().__init__("Session has expired.", "SESSION_001", HTTPStatus.UNAUTHORIZED)


class SessionNotFoundError(PrintBarError):
    def __init__(self) -> None:
        super().__init__("Session not found.", "SESSION_002", HTTPStatus.UNAUTHORIZED)

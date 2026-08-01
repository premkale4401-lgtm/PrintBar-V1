"""
PrintBar Backend — Global Exception Handlers

Maps all PrintBarError subclasses and unexpected exceptions to
standardized JSON API responses.

No stack traces are ever exposed to clients.
All internal errors are logged with full context.

Response format (error):
    {
        "success": false,
        "error": {
            "code": "UPLOAD_001",
            "message": "Only PDF files are supported."
        },
        "requestId": "..."
    }
"""

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.logging import get_logger
from app.exceptions.base import PrintBarError

logger = get_logger(__name__)


def _error_response(
    request: Request,
    status_code: int,
    error_code: str,
    message: str,
) -> JSONResponse:
    """Builds the standard error response envelope."""
    return JSONResponse(
        status_code=status_code,
        content={
            "success": False,
            "error": {
                "code": error_code,
                "message": message,
            },
            "requestId": getattr(request.state, "request_id", None),
        },
    )


async def printbar_exception_handler(
    request: Request,
    exc: PrintBarError,
) -> JSONResponse:
    """
    Handles all custom PrintBarError subclasses.

    Logs the error at the appropriate level and returns a
    structured JSON response without internal details.
    """
    log_fn = logger.warning if exc.status_code < 500 else logger.error
    log_fn(
        "application_error",
        error_code=exc.error_code,
        message=exc.message,
        status_code=exc.status_code,
        path=request.url.path,
        method=request.method,
    )
    return _error_response(request, exc.status_code, exc.error_code, exc.message)


async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    """
    Handles Pydantic v2 validation errors from request parsing.

    Returns a 422 with the first validation error message.
    The full error detail is never exposed.
    """
    errors = exc.errors()
    first_error = errors[0] if errors else {}
    field = ".".join(str(loc) for loc in first_error.get("loc", []))
    msg = first_error.get("msg", "Validation error.")

    logger.warning(
        "validation_error",
        field=field,
        message=msg,
        path=request.url.path,
        error_count=len(errors),
    )

    return _error_response(
        request,
        422,
        "SYS_422",
        f"Validation error on field '{field}': {msg}",
    )


async def http_exception_handler(
    request: Request,
    exc: StarletteHTTPException,
) -> JSONResponse:
    """
    Handles standard HTTP exceptions (404, 405, etc.).
    """
    logger.info(
        "http_exception",
        status_code=exc.status_code,
        detail=exc.detail,
        path=request.url.path,
    )
    return _error_response(
        request,
        exc.status_code,
        f"HTTP_{exc.status_code}",
        str(exc.detail),
    )


async def unhandled_exception_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    """
    Catches all unhandled exceptions as a last resort.

    Logs the full exception with traceback internally.
    The client only receives a generic 500 message.
    """
    logger.exception(
        "unhandled_exception",
        exc_type=type(exc).__name__,
        path=request.url.path,
        method=request.method,
    )
    return _error_response(
        request,
        500,
        "SYS_500",
        "An internal error occurred. Please try again later.",
    )

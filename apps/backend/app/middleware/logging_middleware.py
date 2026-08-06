"""
PrintBar Backend — HTTP Logging Middleware

Logs every HTTP request and response with structured fields.
Request bodies are never logged to prevent accidental secret exposure.

Every log line includes:
    - request_id (injected by RequestIDMiddleware)
    - method
    - path
    - status_code
    - duration_ms
    - client_ip
"""

import time

import structlog
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

logger = structlog.get_logger(__name__)

# Paths excluded from request logging to reduce noise.
_EXCLUDED_PATHS = frozenset({"/health", "/live", "/ready", "/metrics"})


class LoggingMiddleware(BaseHTTPMiddleware):
    """
    Logs all HTTP requests and responses with performance metrics.

    Skips health check endpoints to reduce log volume in production.
    Sensitive headers (Authorization, Cookie) are never logged.
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        if request.url.path in _EXCLUDED_PATHS:
            return await call_next(request)

        start_time = time.perf_counter()

        response: Response = await call_next(request)

        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
        status_code = response.status_code

        log = logger.info if status_code < 400 else logger.warning
        if status_code >= 500:
            log = logger.error

        log(
            "http_request",
            method=request.method,
            path=request.url.path,
            status_code=status_code,
            duration_ms=duration_ms,
            client_ip=_get_client_ip(request),
            query_string=_scrub_query_string(request.url.query) if request.url.query else None,
        )

        return response


def _scrub_query_string(query_string: str) -> str:
    """Masks sensitive query parameters."""
    import urllib.parse

    parsed = urllib.parse.parse_qs(query_string, keep_blank_values=True)
    for sensitive_key in ("token", "secret", "key"):
        if sensitive_key in parsed:
            parsed[sensitive_key] = ["***"]
    return urllib.parse.urlencode(parsed, doseq=True)


def _get_client_ip(request: Request) -> str:
    """
    Extracts the real client IP, respecting Cloudflare and Nginx forwarding headers.

    Args:
        request: Incoming Starlette request.

    Returns:
        Client IP address string.
    """
    forwarded_for = request.headers.get("CF-Connecting-IP")
    if forwarded_for:
        return forwarded_for
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"

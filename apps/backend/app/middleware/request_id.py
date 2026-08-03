"""
PrintBar Backend — Request ID Middleware

Injects a unique UUID into every incoming request and propagates it
through structlog's context variables so all log lines within a request
are correlated.

The X-Request-ID header is returned in every response for client-side
tracing and support debugging.
"""

import uuid

import structlog
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp


class RequestIDMiddleware(BaseHTTPMiddleware):
    """
    Generates or forwards a per-request UUID and binds it to the structlog
    context so all log lines within the request lifecycle include the ID.

    If the incoming request already carries an X-Request-ID header, that
    value is reused (enables end-to-end tracing from frontend through backend).

    The request ID is returned in the X-Request-ID response header.
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        correlation_id = request.headers.get("X-Correlation-ID") or request_id

        # Bind to structlog context so every log line within this request
        # automatically includes the request_id without explicit passing.
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            correlation_id=correlation_id,
        )

        # Store on request state so route handlers can access it if needed.
        request.state.request_id = request_id
        request.state.correlation_id = correlation_id

        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Correlation-ID"] = correlation_id
        return response

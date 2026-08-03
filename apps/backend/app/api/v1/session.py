"""
PrintBar Backend — Session API Endpoints

POST /api/v1/sessions      — Create a guest session (called on kiosk page load).
DELETE /api/v1/sessions/me — Invalidate a guest session (called after job completion).

Session tokens are short-lived JWTs. No login required.
All kiosk print flows require a valid session token.
"""

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import JSONResponse

from app.core.logging import get_logger
from app.core.rate_limit import limiter
from app.dependencies import get_current_guest_session
from app.services.session_service import session_service

logger = get_logger(__name__)
router = APIRouter(prefix="/sessions", tags=["Session"])


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Create a guest session",
    description=(
        "Creates a new anonymous guest session. "
        "Call this immediately when the user lands on the kiosk page (QR scan). "
        "Returns a short-lived JWT that must be sent as Bearer token on all subsequent requests."
    ),
)
@limiter.limit("60/minute")
async def create_session(request: Request) -> JSONResponse:
    """
    Creates a guest session and returns an access token.

    This endpoint requires NO authentication.
    The returned access token must be included as:
        Authorization: Bearer <token>
    on all subsequent API calls in the print flow.

    Returns:
        201: Session created with access token and expiry.
    """
    guest_session = session_service.create_session()

    logger.info("session_created_via_api", session_id=guest_session.session_id)

    return JSONResponse(
        status_code=status.HTTP_201_CREATED,
        content={
            "success": True,
            "data": guest_session.to_dict(),
        },
    )


@router.delete(
    "/me",
    status_code=status.HTTP_200_OK,
    summary="Delete current guest session",
    description=(
        "Marks the current guest session as terminated. "
        "Call this after a successful print job completion. "
        "Since sessions are stateless JWTs, this is a client-side logout — "
        "the frontend should discard the token after calling this."
    ),
)
async def delete_session(
    session_id: str = Depends(get_current_guest_session),
) -> dict:
    """
    Terminates a guest session.

    Since guest sessions are stateless JWTs, the backend cannot truly
    invalidate them server-side without a token blocklist. For the guest
    use-case (short session lifetime, no sensitive account), this is acceptable.
    The frontend must discard the token after calling this endpoint.

    Returns:
        200: Session terminated.
    """
    logger.info("session_deleted_via_api", session_id=session_id)
    return {
        "success": True,
        "message": "Session terminated. Please discard your token.",
    }

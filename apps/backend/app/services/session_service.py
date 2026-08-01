"""
PrintBar Backend — Guest Session Service

Manages ephemeral guest sessions for the kiosk print flow.

A guest session is created when a user lands on the kiosk page (QR scan).
It provides a short-lived JWT that authorizes:
    - File uploads
    - Pricing queries
    - Payment creation

No login or registration is required. Sessions expire automatically.
All data associated with an expired session is eligible for cleanup.

Session lifecycle:
    CREATE → active → (upload → configure → pay → print) → COMPLETED
    CREATE → active → (abandoned after 24h) → EXPIRED → cleanup
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import structlog

from app.core.config import get_settings
from app.core.constants import ROLE_GUEST
from app.core.security import jwt_handler
from app.core.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


class GuestSession:
    """
    Represents an active guest session.

    This is a pure value object — guest sessions are NOT persisted
    in the database (only the session_id is stored in uploaded_files
    and print_jobs for reference and cleanup).

    The JWT token is the session carrier. The backend validates the
    token on every request and extracts the session_id from it.
    """

    __slots__ = ("session_id", "created_at", "expires_at", "access_token")

    def __init__(
        self,
        session_id: str,
        created_at: datetime,
        expires_at: datetime,
        access_token: str,
    ) -> None:
        self.session_id = session_id
        self.created_at = created_at
        self.expires_at = expires_at
        self.access_token = access_token

    def to_dict(self) -> dict:
        return {
            "sessionId": self.session_id,
            "accessToken": self.access_token,
            "expiresAt": self.expires_at.isoformat(),
            "createdAt": self.created_at.isoformat(),
        }


class SessionService:
    """
    Creates and validates guest sessions.

    Responsibilities:
        - Generate a unique session ID.
        - Issue a short-lived JWT token containing the session ID.
        - Validate inbound JWT tokens and extract the session ID.

    Note:
        Guest sessions are intentionally stateless (no DB row).
        The JWT is self-contained and verified by signature alone.
        This eliminates a database round-trip on every request.
    """

    def create_session(self) -> GuestSession:
        """
        Creates a new guest session with a JWT access token.

        Returns:
            GuestSession with token and metadata.
        """
        session_id = str(uuid.uuid4())
        now = datetime.now(tz=UTC)
        expires_at = now + timedelta(hours=settings.GUEST_SESSION_EXPIRE_HOURS)

        access_token = jwt_handler.create_access_token(
            subject=session_id,
            role=ROLE_GUEST,
            session_id=session_id,
            extra_claims={"expires_at": expires_at.isoformat()},
        )

        logger.info("guest_session_created", session_id=session_id)

        return GuestSession(
            session_id=session_id,
            created_at=now,
            expires_at=expires_at,
            access_token=access_token,
        )

    def validate_token(self, token: str) -> str:
        """
        Validates a guest JWT token and returns the session ID.

        Args:
            token: Raw JWT string from Authorization header.

        Returns:
            session_id string extracted from the token claims.

        Raises:
            ValueError: If the token is invalid or expired.
        """
        claims = jwt_handler.verify_token(token)

        if claims.get("role") != ROLE_GUEST:
            logger.warning("session_invalid_role", role=claims.get("role"))
            raise ValueError("Token is not a guest session token.")

        session_id = claims.get("sub")
        if not session_id:
            raise ValueError("Token missing session ID.")

        return session_id


# Module-level singleton.
session_service = SessionService()

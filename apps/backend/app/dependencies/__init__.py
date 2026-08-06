"""
PrintBar Backend — FastAPI Dependencies

Provides reusable FastAPI dependency injection functions for:
    - Database session (get_db)
    - Current guest session (get_current_guest_session)
    - Current admin user (get_current_admin)
    - Required roles (require_role)

Usage:
    @router.post("/uploads")
    async def upload_file(
        db: AsyncSession = Depends(get_db),
        session_id: str = Depends(get_current_guest_session),
    ):
        ...
"""

from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import ROLE_ADMIN, ROLE_SUPER_ADMIN
from app.core.logging import get_logger
from app.database.session import get_db
from app.services.session_service import session_service

logger = get_logger(__name__)

# Re-export get_db for convenience — other modules import from here.
__all__ = [
    "get_db",
    "get_current_guest_session",
    "get_current_admin",
    "require_super_admin",
]

_bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_guest_session(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> str:
    """
    FastAPI dependency that extracts and validates the guest session JWT.

    Reads the Authorization: Bearer <token> header.

    Returns:
        session_id string from the validated JWT claims.

    Raises:
        HTTPException 401: If no token provided or token is invalid.
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "AUTH_001", "message": "Authentication token required."},
        )

    try:
        session_id = session_service.validate_token(credentials.credentials)
        return session_id
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "AUTH_002", "message": str(exc)},
        ) from exc


async def get_current_admin(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:  # noqa: F821
    """
    FastAPI dependency that validates an admin JWT and returns the User.

    Used on all /admin/* routes.

    Returns:
        Authenticated User model instance.

    Raises:
        HTTPException 401: Token invalid or expired.
        HTTPException 403: Token valid but user lacks admin role.
        HTTPException 404: User no longer exists in the database.
    """
    import uuid

    from sqlalchemy import select

    from app.core.security import jwt_handler
    from app.models.user import User

    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "AUTH_001", "message": "Admin authentication required."},
        )

    try:
        claims = jwt_handler.verify_token(credentials.credentials)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "AUTH_002", "message": str(exc)},
        ) from exc

    role = claims.get("role")
    if role not in (ROLE_ADMIN, ROLE_SUPER_ADMIN):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "AUTH_004", "message": "Admin access required."},
        )

    user_id_str = claims.get("sub")
    try:
        user_id = uuid.UUID(user_id_str)
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "AUTH_001", "message": "Invalid token subject."},
        )

    result = await db.execute(select(User).where(User.id == user_id, User.is_active.is_(True)))
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "AUTH_001", "message": "User not found or deactivated."},
        )

    return user


async def require_super_admin(
    current_user: User = Depends(get_current_admin),  # noqa: F821
) -> User:  # noqa: F821
    """
    FastAPI dependency that further restricts to SUPER_ADMIN only.

    Use for destructive or privileged operations:
        - Pricing changes
        - Kiosk deletion
        - User management
    """
    if current_user.role != ROLE_SUPER_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "AUTH_004", "message": "Super admin access required."},
        )
    return current_user

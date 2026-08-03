"""
PrintBar Backend — Admin Authentication Endpoints

POST /api/v1/admin/auth/login   — Admin login (returns JWT pair)
POST /api/v1/admin/auth/refresh — Refresh access token
POST /api/v1/admin/auth/logout  — Revoke refresh token
"""
from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.rate_limit import limiter
from app.core.security import jwt_handler, password_hasher
from app.database.session import get_db
from app.dependencies import get_current_admin
from app.exceptions.base import InvalidCredentialsError, TokenExpiredError
from app.models.refresh_token import RefreshToken
from app.models.user import User

logger = get_logger(__name__)
router = APIRouter(prefix="/admin/auth", tags=["Admin Auth"])
settings = get_settings()


@router.post("/login", summary="Admin login")
@limiter.limit("5/15minutes")
async def admin_login(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    """
    Authenticates an admin user with email and password.

    Returns:
        accessToken:  Short-lived JWT (15 min)
        refreshToken: Long-lived token for renewal (30 days)
        expiresIn:    Access token TTL in seconds
    """
    body = await request.json()
    email = body.get("email", "").strip().lower()
    password = body.get("password", "")

    if not email or not password:
        raise InvalidCredentialsError()

    # Lookup user.
    result = await db.execute(
        select(User).where(User.email == email, User.is_active.is_(True))
    )
    user = result.scalar_one_or_none()

    if not user or not password_hasher.verify(user.password_hash, password):
        logger.warning("admin_login_failed", email=email)
        raise InvalidCredentialsError()

    # Update last login.
    await db.execute(
        update(User)
        .where(User.id == user.id)
        .values(last_login_at=datetime.now(tz=UTC).isoformat())
    )

    # Issue access token.
    access_token = jwt_handler.create_access_token(
        subject=str(user.id),
        role=user.role,
        session_id=str(user.id),
    )

    # Issue refresh token.
    raw_refresh = secrets.token_hex(32)
    refresh_hash = hashlib.sha256(raw_refresh.encode()).hexdigest()
    expires_at = (
        datetime.now(tz=UTC) + timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS)
    ).isoformat()

    refresh_token = RefreshToken(
        user_id=user.id,
        token_hash=refresh_hash,
        expires_at=expires_at,
        user_agent=request.headers.get("user-agent"),
        ip_address=request.client.host if request.client else None,
    )
    db.add(refresh_token)
    await db.commit()

    logger.info("admin_login_success", user_id=str(user.id), email=email)

    return JSONResponse(
        content={
            "success": True,
            "data": {
                "accessToken": access_token,
                "refreshToken": raw_refresh,
                "expiresIn": settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
                "role": user.role,
                "name": user.name,
            },
        }
    )


@router.post("/refresh", summary="Refresh access token")
async def refresh_token(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    """
    Exchanges a valid refresh token for a new access token.

    Implements token rotation: the old refresh token is revoked
    and a new one is issued.
    """
    body = await request.json()
    raw_token = body.get("refreshToken", "")

    if not raw_token:
        raise TokenExpiredError()

    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    now = datetime.now(tz=UTC).isoformat()

    result = await db.execute(
        select(RefreshToken).where(
            RefreshToken.token_hash == token_hash,
            RefreshToken.is_revoked.is_(False),
            RefreshToken.expires_at > now,
        )
    )
    token_record = result.scalar_one_or_none()

    if not token_record:
        raise TokenExpiredError()

    # Revoke the used token (rotation).
    await db.execute(
        update(RefreshToken)
        .where(RefreshToken.id == token_record.id)
        .values(is_revoked=True, revoked_at=now)
    )

    # Load user.
    result = await db.execute(
        select(User).where(User.id == token_record.user_id, User.is_active.is_(True))
    )
    user = result.scalar_one_or_none()
    if not user:
        raise TokenExpiredError()

    # Issue new access token.
    access_token = jwt_handler.create_access_token(
        subject=str(user.id),
        role=user.role,
        session_id=str(user.id),
    )

    # Issue new refresh token.
    new_raw = secrets.token_hex(32)
    new_hash = hashlib.sha256(new_raw.encode()).hexdigest()
    new_expires = (
        datetime.now(tz=UTC) + timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS)
    ).isoformat()

    new_refresh = RefreshToken(
        user_id=user.id,
        token_hash=new_hash,
        expires_at=new_expires,
        user_agent=request.headers.get("user-agent"),
        ip_address=request.client.host if request.client else None,
    )
    db.add(new_refresh)
    await db.commit()

    return JSONResponse(
        content={
            "success": True,
            "data": {
                "accessToken": access_token,
                "refreshToken": new_raw,
                "expiresIn": settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            },
        }
    )


@router.post("/logout", summary="Admin logout")
async def admin_logout(
    request: Request,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Revokes the provided refresh token and logs out the admin.
    """
    body = await request.json()
    raw_token = body.get("refreshToken", "")

    if raw_token:
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        await db.execute(
            update(RefreshToken)
            .where(RefreshToken.token_hash == token_hash)
            .values(is_revoked=True, revoked_at=datetime.now(tz=UTC).isoformat())
        )
        await db.commit()

    logger.info("admin_logout", user_id=str(current_user.id))
    return {"success": True, "message": "Logged out successfully."}

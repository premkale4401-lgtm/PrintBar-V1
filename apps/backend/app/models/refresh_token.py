"""
PrintBar Backend — RefreshToken Model

Stores hashed refresh tokens for admin users.

Security:
    - Only a SHA-256 hash of the refresh token is stored.
    - The raw token is returned once at login and never stored.
    - Tokens expire after 30 days (configurable).
    - Token rotation: each use issues a new token and invalidates the old one.
    - All tokens for a user can be revoked at once (logout all devices).
"""

import uuid

from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import PrintBarBase


class RefreshToken(PrintBarBase):
    """
    Hashed refresh token for admin users.

    Columns:
        user_id:     FK to the owning admin user.
        token_hash:  SHA-256 hash of the raw refresh token.
        expires_at:  ISO UTC timestamp when this token expires.
        is_revoked:  True if the token has been explicitly revoked.
        revoked_at:  Timestamp of revocation.
        user_agent:  Browser/device info for display in security settings.
        ip_address:  Client IP at time of issuance.
        last_used_at: Last time this refresh token was used.
    """

    __tablename__ = "refresh_tokens"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    token_hash: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    expires_at: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    is_revoked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    revoked_at: Mapped[str | None] = mapped_column(String(50), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    last_used_at: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="refresh_tokens")  # noqa: F821

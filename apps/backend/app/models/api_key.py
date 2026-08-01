"""
PrintBar Backend — ApiKey Model

Represents a Raspberry Pi kiosk API key.

API keys are used to authenticate WebSocket connections from kiosks.
The raw key is shown exactly once at registration time.
Only a SHA-256 hash is stored in the database.

Key rotation:
    - Admins can rotate a kiosk's API key via the admin dashboard.
    - The old key is immediately invalidated.
    - The rotation is logged in audit_logs.
"""

import uuid

from sqlalchemy import Boolean, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import PrintBarBase


class ApiKey(PrintBarBase):
    """
    Kiosk API key record (hash only — never the raw key).

    Columns:
        kiosk_id:    FK to the owning kiosk.
        key_hash:    SHA-256 hash of the raw API key.
        key_prefix:  First 8 characters of the raw key (for display/identification).
        is_active:   False when the key has been rotated or revoked.
        description: Optional label for the key.
        last_used_at: Timestamp of last successful authentication.
        revoked_at:  Timestamp of revocation.
        revoke_reason: Reason for revocation.
    """

    __tablename__ = "api_keys"

    kiosk_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("kiosks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    key_hash: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    key_prefix: Mapped[str] = mapped_column(String(16), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    last_used_at: Mapped[str | None] = mapped_column(String(50), nullable=True)
    revoked_at: Mapped[str | None] = mapped_column(String(50), nullable=True)
    revoke_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    kiosk: Mapped["Kiosk"] = relationship("Kiosk", back_populates="api_keys")  # noqa: F821

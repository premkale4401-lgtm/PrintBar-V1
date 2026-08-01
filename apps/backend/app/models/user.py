"""
PrintBar Backend — User Model

Represents admin users of the PrintBar system.
Guest sessions are NOT stored in this table — they use the GuestSession model.

Admin users are created by SUPER_ADMIN via the admin dashboard.
No user self-registration is supported.
"""

from sqlalchemy import Boolean, Enum, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.constants import ROLE_ADMIN, ROLE_SUPER_ADMIN
from app.database.base import PrintBarBase


class User(PrintBarBase):
    """
    Admin and operator users of the PrintBar platform.

    Columns:
        email:       Unique email address used for login.
        name:        Display name.
        password_hash: Argon2id hash of the password.
        role:        Authorization role (ADMIN, SUPER_ADMIN).
        is_active:   Soft-disable without deleting the account.
        last_login_at: UTC timestamp of the last successful login.

    Relationships:
        refresh_tokens: All issued refresh tokens for this user.
        audit_logs:    Audit log entries where this user was the actor.
    """

    __tablename__ = "users"

    email: Mapped[str] = mapped_column(
        String(254),
        nullable=False,
        unique=True,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(512), nullable=False)
    role: Mapped[str] = mapped_column(
        Enum(ROLE_ADMIN, ROLE_SUPER_ADMIN, name="user_role_enum"),
        nullable=False,
        default=ROLE_ADMIN,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_login_at: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Relationships
    refresh_tokens: Mapped[list["RefreshToken"]] = relationship(  # noqa: F821
        "RefreshToken", back_populates="user", cascade="all, delete-orphan"
    )
    audit_logs: Mapped[list["AuditLog"]] = relationship(  # noqa: F821
        "AuditLog", back_populates="user"
    )

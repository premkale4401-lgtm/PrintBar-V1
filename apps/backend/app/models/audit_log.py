"""
PrintBar Backend — AuditLog Model

Immutable, append-only audit trail for all administrative and system actions.

Every significant action is recorded:
    - Admin logins and logouts
    - Pricing changes
    - Job state transitions
    - Payment events
    - Kiosk registration and authentication
    - File deletions
    - API key rotation

This model is NEVER updated or deleted.
Records are retained permanently for legal and compliance purposes.
"""

import uuid

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, UUIDMixin, TimestampMixin


class AuditLog(Base, UUIDMixin, TimestampMixin):
    """
    Immutable audit log entry.

    Columns:
        actor_user_id:   Admin user who performed the action (nullable for system/kiosk actions).
        actor_kiosk_id:  Kiosk that performed the action (nullable for user/system actions).
        actor_type:      "USER", "KIOSK", or "SYSTEM".
        action:          Action code from constants (e.g., AUDIT_JOB_STATUS_CHANGED).
        entity_type:     Entity type affected (e.g., "PrintJob", "Payment").
        entity_id:       UUID of the entity affected.
        print_job_id:    FK to print job if applicable.
        ip_address:      Client IP address.
        result:          "SUCCESS" or "FAILURE".
        details:         JSON blob with additional context.
        error:           Error message if result is FAILURE.
    """

    __tablename__ = "audit_logs"

    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    actor_kiosk_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("kiosks.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    actor_type: Mapped[str] = mapped_column(
        String(16), nullable=False, default="SYSTEM"
    )
    action: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    entity_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    entity_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    print_job_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("print_jobs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    result: Mapped[str] = mapped_column(String(16), nullable=False, default="SUCCESS")
    details: Mapped[str | None] = mapped_column(Text, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    user: Mapped["User | None"] = relationship("User", back_populates="audit_logs")  # noqa: F821
    print_job: Mapped["PrintJob | None"] = relationship("PrintJob", back_populates="audit_logs")  # noqa: F821

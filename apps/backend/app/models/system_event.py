"""
PrintBar Backend — SystemEvent Model

Records significant system-level events such as:
    - Backend startup/shutdown
    - Kiosk going online/offline
    - Printer errors
    - Cleanup worker runs
    - Webhook failures
    - Storage quota warnings

System events are surfaced in the Admin Dashboard under "System" module.
They are not directly triggered by user actions (unlike audit_logs).
"""

from sqlalchemy import Enum, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin, UUIDMixin


class SystemEvent(Base, UUIDMixin, TimestampMixin):
    """
    Platform-level event record.

    Columns:
        event_type:  Category of the event (e.g., "KIOSK_OFFLINE", "BACKEND_STARTUP").
        severity:    INFO, WARNING, ERROR, CRITICAL.
        source:      Service or component that generated the event.
        message:     Human-readable event description.
        details:     JSON blob with structured event data.
        resolved:    True if an alert-type event has been acknowledged/resolved.
        resolved_at: Timestamp of resolution.
    """

    __tablename__ = "system_events"

    event_type: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    severity: Mapped[str] = mapped_column(
        Enum("INFO", "WARNING", "ERROR", "CRITICAL", name="system_event_severity_enum"),
        nullable=False,
        default="INFO",
        index=True,
    )
    source: Mapped[str] = mapped_column(String(128), nullable=False, default="backend")
    message: Mapped[str] = mapped_column(Text, nullable=False)
    details: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolved: Mapped[bool] = mapped_column(
        __import__("sqlalchemy").Boolean, nullable=False, default=False, index=True
    )
    resolved_at: Mapped[str | None] = mapped_column(String(50), nullable=True)

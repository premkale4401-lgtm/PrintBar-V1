"""
PrintBar Backend — HeartbeatLog Model

Rolling log of kiosk heartbeat messages received by the backend.

Every 30 seconds, each Raspberry Pi sends a heartbeat containing:
    - Health metrics (CPU, RAM, disk, temperature)
    - Printer status
    - Active job status

The backend:
    1. Updates the Kiosk record's status and metrics.
    2. Appends a HeartbeatLog entry.
    3. If no heartbeat is received within 90 seconds, marks the kiosk OFFLINE.

Retention: HeartbeatLog entries are retained for 30 days then auto-purged.
"""

import uuid
from decimal import Decimal

from sqlalchemy import Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, UUIDMixin, TimestampMixin


class HeartbeatLog(Base, UUIDMixin, TimestampMixin):
    """
    One heartbeat record from a kiosk.

    Columns:
        kiosk_id:       FK to the reporting kiosk.
        app_version:    Kiosk software version.
        cpu_percent:    CPU utilization percentage.
        ram_percent:    RAM utilization percentage.
        disk_percent:   Disk utilization percentage.
        temperature_c:  CPU temperature in Celsius.
        printer_status: Printer status string at this heartbeat.
        active_job_id:  Current active job ID if printing.
        network_latency_ms: Latency to backend at time of heartbeat.
        extra:          JSON blob for future extension without schema changes.
    """

    __tablename__ = "heartbeat_logs"

    kiosk_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("kiosks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    app_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    cpu_percent: Mapped[float | None] = mapped_column(Float, nullable=True)
    ram_percent: Mapped[float | None] = mapped_column(Float, nullable=True)
    disk_percent: Mapped[float | None] = mapped_column(Float, nullable=True)
    temperature_c: Mapped[float | None] = mapped_column(Float, nullable=True)
    printer_status: Mapped[str | None] = mapped_column(String(64), nullable=True)
    active_job_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    network_latency_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    extra: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    kiosk: Mapped["Kiosk"] = relationship("Kiosk", back_populates="heartbeat_logs")  # noqa: F821

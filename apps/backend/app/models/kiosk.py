"""
PrintBar Backend — Kiosk Model

Represents a Raspberry Pi kiosk unit registered with the PrintBar platform.

Each kiosk is a physical edge node that receives print jobs via WebSocket,
downloads files from Supabase Storage, and controls a CUPS printer.

Authentication:
    Kiosks authenticate with an API key (hashed SHA-256 in the database).
    The raw API key is shown once at registration and then discarded.
"""

from sqlalchemy import Boolean, Enum, Float, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.constants import (
    KIOSK_STATUS_ERROR,
    KIOSK_STATUS_MAINTENANCE,
    KIOSK_STATUS_OFFLINE,
    KIOSK_STATUS_ONLINE,
    KIOSK_STATUS_PRINTING,
)
from app.database.base import PrintBarBase


class Kiosk(PrintBarBase):
    """
    Raspberry Pi kiosk registration record.

    Columns:
        name:            Human-readable kiosk name (e.g., "Main Campus Kiosk").
        location:        Physical location description.
        city:            City where the kiosk is deployed.
        api_key_hash:    SHA-256 hash of the registration API key.
        status:          Current operational status.
        is_active:       Whether the kiosk is enabled for job assignment.
        ws_connected:    True when the kiosk has an active WebSocket connection.
        app_version:     Version of the kiosk client software.
        latitude:        GPS latitude for map display.
        longitude:       GPS longitude for map display.
        last_heartbeat:  ISO timestamp of the last received heartbeat.
        cpu_percent:     CPU utilization at last heartbeat.
        ram_percent:     RAM utilization at last heartbeat.
        disk_percent:    Disk utilization at last heartbeat.
        temperature_c:   CPU temperature in Celsius at last heartbeat.

    Relationships:
        printers:        All printers associated with this kiosk.
        print_jobs:      All print jobs assigned to this kiosk.
        heartbeat_logs:  Rolling heartbeat history.
        api_keys:        All API keys issued to this kiosk.
    """

    __tablename__ = "kiosks"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    location: Mapped[str] = mapped_column(String(512), nullable=False)
    city: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    api_key_hash: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    status: Mapped[str] = mapped_column(
        Enum(
            KIOSK_STATUS_ONLINE,
            KIOSK_STATUS_OFFLINE,
            KIOSK_STATUS_PRINTING,
            KIOSK_STATUS_MAINTENANCE,
            KIOSK_STATUS_ERROR,
            name="kiosk_status_enum",
        ),
        nullable=False,
        default=KIOSK_STATUS_OFFLINE,
        index=True,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    ws_connected: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    app_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    last_heartbeat: Mapped[str | None] = mapped_column(String(50), nullable=True)
    cpu_percent: Mapped[float | None] = mapped_column(Float, nullable=True)
    ram_percent: Mapped[float | None] = mapped_column(Float, nullable=True)
    disk_percent: Mapped[float | None] = mapped_column(Float, nullable=True)
    temperature_c: Mapped[float | None] = mapped_column(Float, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    printers: Mapped[list["Printer"]] = relationship(  # noqa: F821
        "Printer", back_populates="kiosk", cascade="all, delete-orphan"
    )
    print_jobs: Mapped[list["PrintJob"]] = relationship(  # noqa: F821
        "PrintJob", back_populates="kiosk"
    )
    heartbeat_logs: Mapped[list["HeartbeatLog"]] = relationship(  # noqa: F821
        "HeartbeatLog", back_populates="kiosk", cascade="all, delete-orphan"
    )
    api_keys: Mapped[list["ApiKey"]] = relationship(  # noqa: F821
        "ApiKey", back_populates="kiosk", cascade="all, delete-orphan"
    )

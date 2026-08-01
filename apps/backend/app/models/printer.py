"""
PrintBar Backend — Printer Model

Represents a physical printer attached to a Raspberry Pi kiosk.
A kiosk may have one or more printers. Jobs are dispatched to
the CUPS printer name associated with this record.
"""

import uuid

from sqlalchemy import Boolean, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.constants import (
    PRINTER_STATUS_OFFLINE,
    PRINTER_STATUS_OUT_OF_PAPER,
    PRINTER_STATUS_OUT_OF_TONER,
    PRINTER_STATUS_PAPER_JAM,
    PRINTER_STATUS_PRINTING,
    PRINTER_STATUS_READY,
)
from app.database.base import PrintBarBase


class Printer(PrintBarBase):
    """
    Physical printer attached to a kiosk.

    Columns:
        kiosk_id:       Foreign key to the owning kiosk.
        cups_name:      CUPS printer name (used in lp/lpr commands).
        manufacturer:   Printer manufacturer (e.g., "Brother").
        model:          Printer model (e.g., "HL-L2321D").
        status:         Current printer status reported via heartbeat.
        is_default:     True if this is the kiosk's primary printer.
        is_color:       True if the printer supports color printing.
        is_duplex:      True if the printer supports duplex printing.
        paper_level:    Paper remaining percentage (0-100).
        toner_level:    Toner remaining percentage (0-100).
        jobs_printed:   Total number of jobs printed by this printer.
        last_error:     Last error message reported.
        last_error_at:  Timestamp of last error.
    """

    __tablename__ = "printers"

    kiosk_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("kiosks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    cups_name: Mapped[str] = mapped_column(String(255), nullable=False)
    manufacturer: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    model: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    status: Mapped[str] = mapped_column(
        Enum(
            PRINTER_STATUS_READY,
            PRINTER_STATUS_PRINTING,
            PRINTER_STATUS_OFFLINE,
            PRINTER_STATUS_PAPER_JAM,
            PRINTER_STATUS_OUT_OF_PAPER,
            PRINTER_STATUS_OUT_OF_TONER,
            name="printer_status_enum",
        ),
        nullable=False,
        default=PRINTER_STATUS_OFFLINE,
        index=True,
    )
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_color: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_duplex: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    paper_level: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    toner_level: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    jobs_printed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_error_at: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Relationships
    kiosk: Mapped["Kiosk"] = relationship("Kiosk", back_populates="printers")  # noqa: F821
    print_jobs: Mapped[list["PrintJob"]] = relationship(  # noqa: F821
        "PrintJob", back_populates="printer"
    )

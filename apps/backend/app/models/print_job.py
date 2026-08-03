"""
PrintBar Backend — PrintJob Model

Central entity of the PrintBar platform.
A PrintJob is created only after successful payment verification.

State Machine (enforced by backend, not frontend):
    UPLOADED → VALIDATED → PAYMENT_PENDING → PAYMENT_SUCCESS →
    QUEUED → ASSIGNED → DOWNLOADING → READY_TO_PRINT →
    PRINTING → COMPLETED

Terminal states: COMPLETED, FAILED, CANCELLED, PAYMENT_FAILED, DOWNLOAD_FAILED

All state transitions are recorded in the audit_logs table.
"""

import uuid
from decimal import Decimal

from sqlalchemy import Boolean, Enum, ForeignKey, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.constants import (
    COLOR_MODE_BW,
    COLOR_MODE_COLOR,
    JOB_STATUS_ASSIGNED,
    JOB_STATUS_CANCELLED,
    JOB_STATUS_COMPLETED,
    JOB_STATUS_DOWNLOAD_FAILED,
    JOB_STATUS_DOWNLOADING,
    JOB_STATUS_FAILED,
    JOB_STATUS_PAYMENT_FAILED,
    JOB_STATUS_PAYMENT_PENDING,
    JOB_STATUS_PAYMENT_SUCCESS,
    JOB_STATUS_PRINTING,
    JOB_STATUS_QUEUED,
    JOB_STATUS_READY_TO_PRINT,
    JOB_STATUS_UPLOADED,
    JOB_STATUS_VALIDATED,
    PAPER_SIZE_A3,
    PAPER_SIZE_A4,
    PAPER_SIZE_LEGAL,
    PAPER_SIZE_LETTER,
)
from app.database.base import PrintBarBase


class PrintJob(PrintBarBase):
    """
    A single print job from upload to completion.

    Columns:
        session_id:          Guest session that created this job.
        uploaded_file_id:    Reference to the uploaded file.
        kiosk_id:            Kiosk assigned to handle this job (set after QUEUED).
        printer_id:          Specific printer selected (set after ASSIGNED).
        status:              Current state machine status.
        color_mode:          BW or COLOR.
        paper_size:          A4, A3, LETTER, or LEGAL.
        copies:              Number of copies to print.
        duplex:              True for double-sided printing.
        pages_selected:      Number of pages selected for printing.
        pages_per_sheet:     Pages per physical sheet (1, 2, 4, or 6).
        page_range:          Page range string (e.g., "1-5,8,10-12").
        orientation:         portrait or landscape.
        subtotal_inr:        Pre-GST price in INR.
        gst_inr:             GST amount in INR.
        total_inr:           Final total in INR (subtotal + GST).
        started_at:          Timestamp when printing began.
        completed_at:        Timestamp when print confirmed complete.
        failed_at:           Timestamp of failure.
        failure_reason:      Error code if failed.
        retry_count:         Number of retry attempts.
        idempotency_key:     Unique key for idempotent job creation.

    Relationships:
        uploaded_file:  Reference to the uploaded file.
        kiosk:          Assigned kiosk.
        printer:        Assigned printer.
        payment:        Associated payment record.
        audit_logs:     Audit trail for this job.
    """

    __tablename__ = "print_jobs"

    session_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    uploaded_file_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("uploaded_files.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    kiosk_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("kiosks.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    printer_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("printers.id", ondelete="SET NULL"),
        nullable=True,
    )

    # State machine
    status: Mapped[str] = mapped_column(
        Enum(
            JOB_STATUS_UPLOADED,
            JOB_STATUS_VALIDATED,
            JOB_STATUS_PAYMENT_PENDING,
            JOB_STATUS_PAYMENT_SUCCESS,
            JOB_STATUS_QUEUED,
            JOB_STATUS_ASSIGNED,
            JOB_STATUS_DOWNLOADING,
            JOB_STATUS_READY_TO_PRINT,
            JOB_STATUS_PRINTING,
            JOB_STATUS_COMPLETED,
            JOB_STATUS_FAILED,
            JOB_STATUS_CANCELLED,
            JOB_STATUS_PAYMENT_FAILED,
            JOB_STATUS_DOWNLOAD_FAILED,
            name="print_job_status_enum",
        ),
        nullable=False,
        default=JOB_STATUS_UPLOADED,
        index=True,
    )

    # Print settings
    color_mode: Mapped[str] = mapped_column(
        Enum(COLOR_MODE_BW, COLOR_MODE_COLOR, name="color_mode_enum"),
        nullable=False,
        default=COLOR_MODE_BW,
    )
    paper_size: Mapped[str] = mapped_column(
        Enum(PAPER_SIZE_A4, PAPER_SIZE_A3, PAPER_SIZE_LETTER, PAPER_SIZE_LEGAL, name="paper_size_enum"),
        nullable=False,
        default=PAPER_SIZE_A4,
    )
    copies: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    duplex: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    pages_selected: Mapped[int] = mapped_column(Integer, nullable=False)
    pages_per_sheet: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    page_range: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    orientation: Mapped[str] = mapped_column(String(16), nullable=False, default="portrait")

    # Pricing (stored at time of order — never recalculated after payment)
    subtotal_inr: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, default=Decimal("0.00")
    )
    gst_inr: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, default=Decimal("0.00")
    )
    total_inr: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, default=Decimal("0.00")
    )

    # Timeline
    started_at: Mapped[str | None] = mapped_column(String(50), nullable=True)
    completed_at: Mapped[str | None] = mapped_column(String(50), nullable=True)
    failed_at: Mapped[str | None] = mapped_column(String(50), nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Idempotency & Tracing
    idempotency_key: Mapped[str] = mapped_column(
        String(128), nullable=False, unique=True, index=True
    )
    correlation_id: Mapped[str] = mapped_column(
        String(128), nullable=False, default="unknown", index=True
    )

    # Relationships
    uploaded_file: Mapped["UploadedFile"] = relationship(  # noqa: F821
        "UploadedFile", back_populates="print_jobs"
    )
    kiosk: Mapped["Kiosk | None"] = relationship("Kiosk", back_populates="print_jobs")  # noqa: F821
    printer: Mapped["Printer | None"] = relationship("Printer", back_populates="print_jobs")  # noqa: F821
    payment: Mapped["Payment | None"] = relationship(  # noqa: F821
        "Payment", back_populates="print_job", uselist=False
    )
    audit_logs: Mapped[list["AuditLog"]] = relationship(  # noqa: F821
        "AuditLog", back_populates="print_job"
    )

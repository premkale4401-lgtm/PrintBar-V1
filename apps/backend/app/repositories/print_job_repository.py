"""
PrintBar Backend — Print Job Repository

Data access layer for PrintJob records.
Implements the state machine transition guard.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.exceptions.base import InvalidStateTransition, JobNotFoundError
from app.models.print_job import PrintJob

logger = get_logger(__name__)

# Valid state machine transitions.
# Key: current status → Value: set of allowed next statuses.
VALID_TRANSITIONS: dict[str, set[str]] = {
    "UPLOADED":         {"VALIDATED", "CANCELLED"},
    "VALIDATED":        {"PAYMENT_PENDING", "CANCELLED"},
    "PAYMENT_PENDING":  {"PAYMENT_SUCCESS", "PAYMENT_FAILED", "CANCELLED"},
    "PAYMENT_SUCCESS":  {"QUEUED"},
    "QUEUED":           {"ASSIGNED", "CANCELLED"},
    "ASSIGNED":         {"DOWNLOADING", "QUEUED"},  # QUEUED = re-queue on kiosk failure
    "DOWNLOADING":      {"READY_TO_PRINT", "DOWNLOAD_FAILED"},
    "READY_TO_PRINT":   {"PRINTING"},
    "PRINTING":         {"COMPLETED", "FAILED"},
    # Terminal states — no further transitions.
    "COMPLETED":        set(),
    "FAILED":           set(),
    "CANCELLED":        set(),
    "PAYMENT_FAILED":   set(),
    "DOWNLOAD_FAILED":  {"QUEUED"},  # Allow re-queue after download failure.
}


class PrintJobRepository:
    """
    Repository for PrintJob CRUD and state machine operations.

    Args:
        db: SQLAlchemy async session.
    """

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def create(
        self,
        session_id: str,
        uploaded_file_id: uuid.UUID,
        color_mode: str,
        paper_size: str,
        copies: int,
        duplex: bool,
        pages_selected: int,
        pages_per_sheet: int,
        page_range: str | None,
        orientation: str,
        subtotal_inr: object,
        gst_inr: object,
        total_inr: object,
        idempotency_key: str,
        correlation_id: str = "unknown",
    ) -> PrintJob:
        """Creates a new PrintJob in UPLOADED status."""
        job = PrintJob(
            session_id=session_id,
            uploaded_file_id=uploaded_file_id,
            color_mode=color_mode,
            paper_size=paper_size,
            copies=copies,
            duplex=duplex,
            pages_selected=pages_selected,
            pages_per_sheet=pages_per_sheet,
            page_range=page_range,
            orientation=orientation,
            subtotal_inr=subtotal_inr,  # type: ignore[arg-type]
            gst_inr=gst_inr,  # type: ignore[arg-type]
            total_inr=total_inr,  # type: ignore[arg-type]
            idempotency_key=idempotency_key,
            correlation_id=correlation_id,
            status="UPLOADED",
        )
        self._db.add(job)
        await self._db.flush()

        logger.info(
            "print_job_created",
            job_id=str(job.id),
            session_id=session_id,
            total_inr=str(total_inr),
        )
        return job

    async def get_by_id(self, job_id: uuid.UUID) -> PrintJob | None:
        result = await self._db.execute(
            select(PrintJob).where(PrintJob.id == job_id)
        )
        return result.scalar_one_or_none()

    async def get_by_id_and_session(
        self, job_id: uuid.UUID, session_id: str
    ) -> PrintJob | None:
        result = await self._db.execute(
            select(PrintJob).where(
                PrintJob.id == job_id,
                PrintJob.session_id == session_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_by_idempotency_key(self, key: str) -> PrintJob | None:
        result = await self._db.execute(
            select(PrintJob).where(PrintJob.idempotency_key == key)
        )
        return result.scalar_one_or_none()

    async def get_queued_jobs(self) -> list[PrintJob]:
        """Returns all jobs in QUEUED status, ordered by creation time (FIFO)."""
        result = await self._db.execute(
            select(PrintJob)
            .where(PrintJob.status == "QUEUED")
            .order_by(PrintJob.created_at.asc())
        )
        return list(result.scalars().all())

    async def get_active_uncompleted_jobs(self) -> list[PrintJob]:
        """Returns all jobs in active non-terminal statuses."""
        result = await self._db.execute(
            select(PrintJob)
            .where(PrintJob.status.in_(["PAYMENT_PENDING", "QUEUED", "ASSIGNED", "DOWNLOADING", "READY_TO_PRINT", "PRINTING"]))
            .order_by(PrintJob.created_at.asc())
        )
        return list(result.scalars().all())

    async def transition(
        self, job_id: uuid.UUID, to_status: str, **extra_fields: object
    ) -> PrintJob:
        """
        Transitions a job to a new status, enforcing the state machine.

        Args:
            job_id:        UUID of the job to transition.
            to_status:     Target status string.
            **extra_fields: Additional fields to update (e.g., kiosk_id, started_at).

        Returns:
            Updated PrintJob instance.

        Raises:
            JobNotFoundError:        If the job does not exist.
            InvalidStateTransition: If the transition is not allowed.
        """
        job = await self.get_by_id(job_id)
        if job is None:
            raise JobNotFoundError()

        allowed = VALID_TRANSITIONS.get(job.status, set())
        if to_status not in allowed:
            raise InvalidStateTransition(job.status, to_status)

        values: dict = {"status": to_status}
        values.update(extra_fields)

        await self._db.execute(
            update(PrintJob)
            .where(PrintJob.id == job_id)
            .values(**values)
        )

        # Insert audit log for the transition.
        import json
        from app.models.audit_log import AuditLog
        audit_details = json.dumps({"from": job.status, "to": to_status})
        audit_log = AuditLog(
            actor_type="SYSTEM",
            action="JOB_STATE_CHANGED",
            entity_type="PrintJob",
            entity_id=str(job.id),
            print_job_id=job.id,
            details=audit_details,
        )
        self._db.add(audit_log)

        # Refresh the instance.
        await self._db.refresh(job)

        logger.info(
            "print_job_transitioned",
            job_id=str(job_id),
            from_status=job.status,
            to_status=to_status,
        )
        logger.info("DEBUG_PAYMENT: print_job_repository transition executed", job_id=str(job_id), from_status=job.status, to_status=to_status)
        return job

    async def assign_to_kiosk(
        self, job_id: uuid.UUID, kiosk_id: uuid.UUID, printer_id: uuid.UUID
    ) -> PrintJob:
        """Transitions a job from QUEUED to ASSIGNED with kiosk/printer assignment."""
        return await self.transition(
            job_id,
            "ASSIGNED",
            kiosk_id=kiosk_id,
            printer_id=printer_id,
        )

    async def mark_completed(self, job_id: uuid.UUID) -> PrintJob:
        """Marks a job as COMPLETED and records completion timestamp."""
        return await self.transition(
            job_id,
            "COMPLETED",
            completed_at=datetime.now(tz=UTC).isoformat(),
        )

    async def mark_failed(self, job_id: uuid.UUID, reason: str) -> PrintJob:
        """Marks a job as FAILED with a reason."""
        return await self.transition(
            job_id,
            "FAILED",
            failure_reason=reason,
            failed_at=datetime.now(tz=UTC).isoformat(),
        )

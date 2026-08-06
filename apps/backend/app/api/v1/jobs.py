"""
PrintBar Backend — Print Jobs API Endpoints

GET  /api/v1/jobs/{id}         — Get job details + status (guest session)
GET  /api/v1/jobs/{id}/receipt — Download receipt (after COMPLETED)
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_db
from app.dependencies import get_current_guest_session
from app.exceptions.base import JobNotFoundError
from app.repositories.print_job_repository import PrintJobRepository

router = APIRouter(prefix="/jobs", tags=["Jobs"])


@router.get(
    "/{job_id}",
    summary="Get print job status",
    description=(
        "Returns the full status of a print job. "
        "Used by the frontend to poll job progress after payment."
    ),
)
async def get_job(
    job_id: uuid.UUID,
    session_id: str = Depends(get_current_guest_session),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Returns job details for the authenticated session.

    Frontend uses this to drive the progress screen:
        QUEUED → showing queue position
        ASSIGNED / DOWNLOADING / PRINTING → showing progress
        COMPLETED → showing success + receipt option
        FAILED / CANCELLED → showing error
    """
    repo = PrintJobRepository(db)
    job = await repo.get_by_id_and_session(job_id, session_id)
    if not job:
        raise JobNotFoundError()

    return {
        "success": True,
        "data": {
            "jobId": str(job.id),
            "status": job.status,
            "colorMode": job.color_mode,
            "paperSize": job.paper_size,
            "copies": job.copies,
            "duplex": job.duplex,
            "pagesSelected": job.pages_selected,
            "subtotalInr": str(job.subtotal_inr),
            "gstInr": str(job.gst_inr),
            "totalInr": str(job.total_inr),
            "kioskId": str(job.kiosk_id) if job.kiosk_id else None,
            "startedAt": job.started_at,
            "completedAt": job.completed_at,
            "failureReason": job.failure_reason,
            "createdAt": job.created_at.isoformat() if job.created_at else None,
        },
    }

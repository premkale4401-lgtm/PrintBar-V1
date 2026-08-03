"""
PrintBar Backend — Development-Only Payment Bypass

POST /api/v1/payments/dev/complete

Bypasses the payment gateway for local development when Razorpay credentials
are not yet configured. Immediately marks the payment as SUCCESS and
transitions the job to QUEUED.

CRITICAL SAFETY GUARDS:
    - Only active when ENVIRONMENT=development (never staging or production).
    - Returns HTTP 403 if called in staging or production.
    - Not included in production OpenAPI docs.
    - The endpoint name ("dev/complete") makes intent unambiguous.

Usage:
    POST /api/v1/payments/dev/complete?job_id=<uuid>
    (Requires a valid guest session token like all other payment endpoints.)
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.database.session import get_db
from app.dependencies import get_current_guest_session
from app.repositories.payment_repository import PaymentRepository
from app.repositories.print_job_repository import PrintJobRepository

logger = get_logger(__name__)
router = APIRouter(tags=["Development"])
settings = get_settings()


@router.post(
    "/payments/dev/complete",
    status_code=status.HTTP_200_OK,
    summary="[DEV ONLY] Bypass payment gateway and complete payment immediately",
    description=(
        "Development-only endpoint. Returns 403 in staging/production. "
        "Marks payment as SUCCESS and transitions job to QUEUED without "
        "contacting any payment gateway."
    ),
    include_in_schema=not settings.is_production,
)
async def dev_complete_payment(
    job_id: uuid.UUID,
    session_id: str = Depends(get_current_guest_session),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    """
    DEV ONLY: Bypasses payment gateway and marks payment as SUCCESS immediately.
    """
    # Hard guard — only allow in development OR when mock payment provider is active.
    # This prevents accidental use in production with real payment gateways.
    is_dev = settings.ENVIRONMENT == "development"
    is_mock = settings.is_mock_payment

    if not is_dev and not is_mock:
        logger.warning(
            "dev_complete_payment_blocked",
            environment=settings.ENVIRONMENT,
            payment_provider=settings.PAYMENT_PROVIDER,
        )
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={
                "success": False,
                "error": {
                    "code": "DEV_001",
                    "message": (
                        "This endpoint requires ENVIRONMENT=development or "
                        "PAYMENT_PROVIDER=mock."
                    ),
                },
            },
        )


    logger.warning(
        "dev_payment_bypass_used",
        job_id=str(job_id),
        session_id=session_id[:8],
        warning="DEV MODE ONLY — Never use in production.",
    )

    job_repo = PrintJobRepository(db)
    pay_repo = PaymentRepository(db)

    # Verify job belongs to this session.
    job = await job_repo.get_by_id_and_session(job_id, session_id)
    if not job:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={
                "success": False,
                "error": {"code": "JOB_001", "message": "Job not found."},
            },
        )

    payment = await pay_repo.get_by_print_job_id(job_id)
    if not payment:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={
                "success": False,
                "error": {"code": "PAY_006", "message": "No payment found for this job."},
            },
        )

    # Already done — idempotent.
    if payment.status == "SUCCESS":
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "success": True,
                "message": "Payment already marked SUCCESS.",
                "data": {"jobId": str(job_id), "status": "QUEUED"},
            },
        )

    # Mark payment SUCCESS (skip gateway entirely).
    now = datetime.now(tz=UTC).isoformat()
    await pay_repo.mark_success(
        payment_id=payment.id,
        gateway_txn_id=f"dev_bypass_{uuid.uuid4().hex[:12]}",
        payment_mode="DEV_BYPASS",
        vpa=None,
        bank_ref=None,
        signature_prefix="dev_mode_bypass...",
    )

    # Transition job to QUEUED.
    if job.status == "PAYMENT_PENDING":
        await job_repo.transition(job.id, "PAYMENT_SUCCESS")
        await job_repo.transition(job.id, "QUEUED")
    elif job.status == "PAYMENT_SUCCESS":
        await job_repo.transition(job.id, "QUEUED")

    logger.info(
        "dev_payment_bypass_completed",
        job_id=str(job_id),
        payment_id=str(payment.id),
    )

    await db.commit()

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "success": True,
            "data": {
                "jobId": str(job_id),
                "status": "QUEUED",
                "message": "Dev bypass: Payment marked SUCCESS and job queued.",
            },
        },
    )

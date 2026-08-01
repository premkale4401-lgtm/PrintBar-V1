"""
PrintBar Backend — Payment & Checkout API Endpoints

POST /api/v1/payments/create-order   — Create Razorpay order (returns orderId + keyId)
POST /api/v1/payments/verify         — Verify Razorpay HMAC-SHA256 signature
GET  /api/v1/payments/{job_id}/status — Poll payment + job status

Legacy:
POST /api/v1/checkout                — Kept for backward compat (redirects to create-order flow)
POST /api/v1/payments/webhook        — Kept for Easebuzz legacy PENDING payments
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.database.session import get_db
from app.dependencies import get_current_guest_session
from app.exceptions.base import (
    DuplicatePaymentError,
    InvalidPaymentSignatureError,
    JobNotFoundError,
    PaymentAmountMismatchError,
    PaymentGatewayError,
    PaymentOrderNotFoundError,
)
from app.repositories.payment_repository import PaymentRepository
from app.repositories.print_job_repository import PrintJobRepository
from app.services.payment_service import PaymentService

logger = get_logger(__name__)
router = APIRouter(tags=["Payment"])
settings = get_settings()


# ─── Request / Response Schemas ───────────────────────────────────────────────

class RazorpayVerifyRequest(BaseModel):
    """
    Payload sent by the frontend after the Razorpay modal completes.

    The frontend receives all three IDs directly from Razorpay's
    payment handler callback and must relay them to this endpoint
    for server-side signature verification.
    """

    razorpay_order_id: str = Field(
        ...,
        description="Razorpay order ID (e.g. order_XXXX). Returned by create-order.",
    )
    razorpay_payment_id: str = Field(
        ...,
        description="Razorpay payment ID (e.g. pay_XXXX). Set by Razorpay after payment.",
    )
    razorpay_signature: str = Field(
        ...,
        description=(
            "HMAC-SHA256 signature from Razorpay callback. "
            "Verified server-side with KEY_SECRET — never trusted from client."
        ),
    )
    job_id: str = Field(
        ...,
        description="Our internal print job UUID. Links payment to the correct job.",
    )


# ─── Razorpay: Create Order ───────────────────────────────────────────────────

@router.post(
    "/payments/create-order",
    status_code=status.HTTP_201_CREATED,
    summary="Create Razorpay payment order",
    description=(
        "Creates a print job and a Razorpay order. "
        "Returns the Razorpay order ID, amount in paise, currency, and the public KEY_ID. "
        "The frontend uses these to open the Razorpay Standard Checkout modal. "
        "KEY_SECRET is never returned to the frontend. "
        "Requires a valid guest session token."
    ),
)
async def create_razorpay_order(
    file_id: uuid.UUID,
    color_mode: str = "BW",
    paper_size: str = "A4",
    copies: int = 1,
    duplex: bool = False,
    pages_selected: int = 1,
    pages_per_sheet: int = 1,
    orientation: str = "portrait",
    page_range: str | None = None,
    idempotency_key: str | None = None,
    session_id: str = Depends(get_current_guest_session),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    """
    Creates a print job and a Razorpay payment order.

    The backend:
        1. Validates the uploaded file belongs to the session.
        2. Recalculates price (never trusts frontend amounts).
        3. Creates PrintJob in PAYMENT_PENDING state.
        4. Creates Payment record.
        5. Calls Razorpay Orders API with Basic Auth.
        6. Returns Razorpay order details + public KEY_ID to frontend.

    The frontend opens the Razorpay modal and calls /payments/verify on success.
    """
    service = PaymentService(db)

    try:
        result = await service.create_razorpay_order(
            session_id=session_id,
            file_id=file_id,
            color_mode=color_mode.upper(),
            paper_size=paper_size.upper(),
            copies=copies,
            duplex=duplex,
            pages_selected=pages_selected,
            pages_per_sheet=pages_per_sheet,
            page_range=page_range,
            orientation=orientation,
            idempotency_key=idempotency_key,
        )
    except PaymentAmountMismatchError:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "success": False,
                "error": {
                    "code": "PAY_003",
                    "message": "Order amount is below the minimum required (₹1.00).",
                },
            },
        )
    except PaymentGatewayError:
        return JSONResponse(
            status_code=status.HTTP_502_BAD_GATEWAY,
            content={
                "success": False,
                "error": {
                    "code": "PAY_005",
                    "message": "Payment gateway error. Please try again.",
                },
            },
        )

    return JSONResponse(
        status_code=status.HTTP_201_CREATED,
        content={"success": True, "data": result},
    )


# ─── Razorpay: Verify Payment ─────────────────────────────────────────────────

@router.post(
    "/payments/verify",
    status_code=status.HTTP_200_OK,
    summary="Verify Razorpay payment signature",
    description=(
        "Verifies the Razorpay HMAC-SHA256 payment signature server-side. "
        "Called by the frontend immediately after the Razorpay modal handler fires. "
        "On success: marks payment as SUCCESS and transitions print job to QUEUED. "
        "Requires a valid guest session token."
    ),
)
async def verify_razorpay_payment(
    request_body: RazorpayVerifyRequest,
    session_id: str = Depends(get_current_guest_session),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    """
    Verifies a Razorpay payment and queues the print job.

    Security:
        - HMAC-SHA256 signature is verified server-side with KEY_SECRET.
        - Constant-time comparison prevents timing attacks.
        - Amount is re-validated against the stored Payment record.
        - Duplicate verification attempts are rejected.
        - Raw payload is stored in webhook log before any processing.

    Returns 200 on success. Returns 4xx on verification failure.
    """
    try:
        job_uuid = uuid.UUID(request_body.job_id)
    except (ValueError, AttributeError):
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "success": False,
                "error": {"code": "PAY_006", "message": "Invalid job ID format."},
            },
        )

    service = PaymentService(db)

    try:
        result = await service.verify_razorpay_payment(
            razorpay_order_id=request_body.razorpay_order_id,
            razorpay_payment_id=request_body.razorpay_payment_id,
            razorpay_signature=request_body.razorpay_signature,
            job_id=job_uuid,
        )
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={"success": True, "data": result},
        )

    except InvalidPaymentSignatureError:
        logger.warning(
            "verify_endpoint_signature_failed",
            job_id=request_body.job_id,
            order_id=request_body.razorpay_order_id,
        )
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "success": False,
                "error": {
                    "code": "PAY_001",
                    "message": "Payment signature verification failed.",
                },
            },
        )

    except DuplicatePaymentError:
        # Idempotent — return success for already-processed payments.
        logger.info(
            "verify_endpoint_duplicate_ignored",
            job_id=request_body.job_id,
        )
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={"success": True, "message": "Already processed."},
        )

    except PaymentOrderNotFoundError:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={
                "success": False,
                "error": {"code": "PAY_006", "message": "Payment order not found."},
            },
        )

    except PaymentAmountMismatchError:
        logger.error(
            "verify_endpoint_amount_mismatch",
            job_id=request_body.job_id,
        )
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "success": False,
                "error": {
                    "code": "PAY_003",
                    "message": "Payment amount does not match the order.",
                },
            },
        )

    except Exception as exc:
        logger.exception("verify_endpoint_unexpected_error", error=str(exc))
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"success": False, "error": {"code": "SYS_000"}},
        )


# ─── Status Polling ───────────────────────────────────────────────────────────

@router.get(
    "/payments/{job_id}/status",
    summary="Get payment status for a job",
    description=(
        "Polls the payment and job status for a print job. "
        "Call every 3 seconds after the Razorpay modal closes "
        "until jobStatus reaches QUEUED, PRINTING, or COMPLETED."
    ),
)
async def get_payment_status(
    job_id: uuid.UUID,
    session_id: str = Depends(get_current_guest_session),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Returns the current payment and job status for polling.

    Returns:
        paymentStatus: CREATED | PENDING | SUCCESS | FAILED | EXPIRED
        jobStatus:     Current print job status
    """
    job_repo = PrintJobRepository(db)
    pay_repo = PaymentRepository(db)

    job = await job_repo.get_by_id_and_session(job_id, session_id)
    if not job:
        raise JobNotFoundError()

    payment = await pay_repo.get_by_print_job_id(job_id)

    return {
        "success": True,
        "data": {
            "jobId": str(job.id),
            "jobStatus": job.status,
            "paymentStatus": payment.status if payment else "CREATED",
            "totalInr": str(job.total_inr),
            "paidAt": payment.paid_at if payment else None,
        },
    }

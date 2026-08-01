"""
PrintBar Backend — Payment & Checkout API Endpoints

POST /api/v1/checkout                 — Initiate payment (creates job + payment)
POST /api/v1/payments/webhook         — Easebuzz webhook receiver
GET  /api/v1/payments/{job_id}/status — Poll payment status
"""
from __future__ import annotations

import uuid
from urllib.parse import urljoin

from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import JSONResponse, RedirectResponse
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
)
from app.repositories.payment_repository import PaymentRepository
from app.repositories.print_job_repository import PrintJobRepository
from app.services.payment_service import PaymentService

logger = get_logger(__name__)
router = APIRouter(tags=["Payment"])
settings = get_settings()


@router.post(
    "/checkout",
    status_code=status.HTTP_201_CREATED,
    summary="Initiate payment checkout",
    description=(
        "Creates a print job and initiates an Easebuzz payment. "
        "Returns the Easebuzz payment URL to redirect the user to. "
        "Requires a valid guest session token."
    ),
)
async def initiate_checkout(
    request: Request,
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
    Initiates the checkout flow for a validated uploaded file.

    The backend:
        1. Recalculates price (never trusts frontend amount)
        2. Creates PrintJob in QUEUED state
        3. Creates Payment record
        4. Calls Easebuzz to get payment URL
        5. Returns payment URL

    The frontend redirects the user to paymentUrl.
    Easebuzz calls our webhook on completion.
    """
    # Build webhook callback URLs.
    base = str(request.base_url).rstrip("/")
    success_url = f"{base}{settings.API_V1_PREFIX}/payments/webhook"
    failure_url = f"{base}{settings.API_V1_PREFIX}/payments/webhook"

    service = PaymentService(db)
    result = await service.initiate_checkout(
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
        success_url=success_url,
        failure_url=failure_url,
        idempotency_key=idempotency_key,
    )

    return JSONResponse(
        status_code=status.HTTP_201_CREATED,
        content={"success": True, "data": result},
    )


@router.post(
    "/payments/webhook",
    status_code=status.HTTP_200_OK,
    summary="Easebuzz payment webhook",
    description=(
        "Receives POST callbacks from Easebuzz after payment success or failure. "
        "This endpoint is called by Easebuzz — not by the frontend. "
        "Verifies HMAC-SHA512 signature before processing."
    ),
)
async def payment_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    """
    Processes an Easebuzz payment webhook.

    Easebuzz sends form-encoded POST data to this endpoint.
    The raw payload is always stored before any processing.

    Returns 200 to Easebuzz regardless of processing outcome
    (prevents Easebuzz from retrying valid but rejected webhooks).
    """
    # Parse form data from Easebuzz.
    form_data = await request.form()
    payload = dict(form_data)

    logger.info(
        "webhook_received",
        txnid=payload.get("txnid"),
        status=payload.get("status"),
    )

    service = PaymentService(db)

    try:
        result = await service.process_webhook(payload)
        return JSONResponse(content={"success": True, "data": result})

    except InvalidPaymentSignatureError:
        # Log and return 200 — invalid signature is a security event, not a retry case.
        logger.warning("webhook_rejected_invalid_signature")
        return JSONResponse(
            content={"success": False, "error": {"code": "PAY_001", "message": "Signature invalid"}},
        )
    except DuplicatePaymentError:
        return JSONResponse(content={"success": True, "message": "Already processed"})
    except PaymentAmountMismatchError:
        logger.error("webhook_amount_mismatch")
        return JSONResponse(
            content={"success": False, "error": {"code": "PAY_003", "message": "Amount mismatch"}},
        )
    except Exception as exc:
        logger.exception("webhook_unexpected_error", error=str(exc))
        # Return 200 to prevent Easebuzz retries while we investigate.
        return JSONResponse(content={"success": False, "error": {"code": "SYS_000"}})


@router.get(
    "/payments/{job_id}/status",
    summary="Get payment status for a job",
    description="Polls the payment status for a print job. Used by the frontend to detect completion.",
)
async def get_payment_status(
    job_id: uuid.UUID,
    session_id: str = Depends(get_current_guest_session),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Returns the current payment and job status for polling.

    The frontend polls this every 3 seconds after redirecting back from Easebuzz.

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

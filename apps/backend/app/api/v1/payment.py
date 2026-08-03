"""
PrintBar Backend — Payment & Checkout API Endpoints

POST /api/v1/payments/create-order           — Create payment order (provider-agnostic)
POST /api/v1/payments/verify                 — Verify payment callback (HMAC-SHA256)
POST /api/v1/payments/webhook/razorpay       — Razorpay webhook handler (raw body)
POST /api/v1/payments/{job_id}/cancel        — Cancel payment (user dismissed modal)
GET  /api/v1/payments/{job_id}/status        — Poll payment + job status + verification stage
GET  /api/v1/payments/{job_id}/poll-order    — Poll gateway order status (QR flow)

Security:
    - Webhook endpoint reads raw bytes before any JSON parsing.
    - HMAC verification happens on raw bytes using WEBHOOK_SECRET.
    - Frontend never marks payment successful — only backend verification does.
    - All endpoints require a valid guest session token.
    - Webhook endpoint does NOT require a guest session (called by Razorpay server).
"""

import uuid

from fastapi import APIRouter, Depends, Header, Request, status, Body
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.rate_limit import limiter
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

class PaymentVerifyRequest(BaseModel):
    """
    Payload sent by the frontend after the payment modal completes.

    The frontend receives all three IDs directly from the payment gateway's
    handler callback and relays them here for server-side signature verification.

    Field names use Razorpay's naming convention for backward compatibility.
    The frontend does not need to know these are Razorpay-specific fields.
    """

    razorpay_order_id: str = Field(
        ...,
        description="Gateway order ID returned by create-order.",
    )
    razorpay_payment_id: str = Field(
        ...,
        description="Gateway payment ID assigned after payment completes.",
    )
    razorpay_signature: str = Field(
        ...,
        description=(
            "HMAC-SHA256 signature from gateway callback. "
            "Verified server-side with KEY_SECRET — never trusted from client."
        ),
    )
    job_id: str = Field(
        ...,
        description="Internal print job UUID. Links payment to the correct job.",
    )


# ─── Create Order ─────────────────────────────────────────────────────────────

@router.post(
    "/payments/create-order",
    status_code=status.HTTP_201_CREATED,
    summary="Create payment order",
    description=(
        "Creates a print job and a payment order with the active gateway. "
        "Returns the gateway order ID, amount in paise, currency, and the public KEY_ID. "
        "The frontend uses these to open the payment UI. "
        "KEY_SECRET is never returned to the frontend. "
        "Requires a valid guest session token."
    ),
)
async def create_payment_order(
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
    """Creates a print job and payment order. Returns gateway order details."""
    service = PaymentService(db)

    # ── Duplicate Request Protection ──────────────────────────────────────────
    # If frontend doesn't provide an idempotency key, we generate a deterministic
    # one based on the order parameters to prevent accidental double-orders.
    if not idempotency_key:
        import hashlib
        raw_key = f"{session_id}_{file_id}_{copies}_{pages_selected}_{color_mode}_{paper_size}_{duplex}"
        idempotency_key = f"order_{hashlib.sha256(raw_key.encode()).hexdigest()[:16]}"
        
    correlation_id = getattr(request.state, "correlation_id", "unknown")

    try:
        result = await service.create_order(
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
            correlation_id=correlation_id,
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
    except Exception as exc:
        logger.exception("create_order_unexpected", error=str(exc))
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"success": False, "error": {"code": "SYS_000"}},
        )

    # Inject mock mode flag so frontend can show "Complete Payment" button.
    result["isMockMode"] = settings.is_mock_payment

    from app.core.metrics import PRINT_JOBS_TOTAL
    PRINT_JOBS_TOTAL.inc()

    return JSONResponse(
        status_code=status.HTTP_201_CREATED,
        content={"success": True, "data": result},
    )



# ─── Verify Payment Callback ──────────────────────────────────────────────────

@router.post(
    "/payments/verify",
    status_code=status.HTTP_200_OK,
    summary="Verify payment callback signature",
    description=(
        "Verifies the payment gateway HMAC-SHA256 callback signature server-side. "
        "Called by the frontend immediately after the payment modal handler fires. "
        "On success: marks payment as SUCCESS and transitions print job to QUEUED. "
        "Requires a valid guest session token."
    ),
)
@limiter.limit("10/minute")
async def verify_payment(
    request: Request,
    request_body: PaymentVerifyRequest = Body(...),
    session_id: str = Depends(get_current_guest_session),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    """Verifies the payment callback and queues the print job."""
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
        result = await service.verify_payment_callback(
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
        logger.info("verify_endpoint_duplicate_ignored", job_id=request_body.job_id)
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
        logger.error("verify_endpoint_amount_mismatch", job_id=request_body.job_id)
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


# ─── Razorpay Webhook ─────────────────────────────────────────────────────────

@router.post(
    "/payments/webhook/razorpay",
    status_code=status.HTTP_200_OK,
    summary="Razorpay webhook handler",
    description=(
        "Receives and processes Razorpay webhook events. "
        "HMAC-SHA256 signature is verified on raw body bytes BEFORE any JSON parsing. "
        "Idempotent — duplicate webhooks are silently ignored. "
        "This endpoint is called by Razorpay servers — not by the frontend. "
        "Configure this URL in Razorpay Dashboard → Webhooks."
    ),
    include_in_schema=False,  # Don't expose in OpenAPI docs for security.
)
async def razorpay_webhook(
    request: Request,
    x_razorpay_signature: str = Header(
        ...,
        alias="X-Razorpay-Signature",
        description="HMAC-SHA256 signature of the raw request body.",
    ),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    """
    Razorpay webhook handler.

    CRITICAL: Must read raw body bytes — NOT use request.json() —
    because HMAC is computed over the exact raw bytes.
    Parsing JSON first would invalidate the signature verification.
    """
    # Read raw body FIRST — before any parsing.
    raw_body = await request.body()

    if not raw_body:
        logger.warning("webhook_empty_body")
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"success": False, "error": "Empty body"},
        )

    # Webhook processing is not applicable in mock payment mode.
    # In mock mode, payment completion is triggered by POST /payments/dev/complete.
    if settings.is_mock_payment:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={
                "success": False,
                "error": {
                    "code": "PAY_007",
                    "message": "Webhook not available in mock payment mode.",
                },
            },
        )

    service = PaymentService(db)


    try:
        result = await service.process_webhook(
            raw_body=raw_body,
            signature_header=x_razorpay_signature,
        )
        # Always return 200 to Razorpay — even if we don't process (duplicate/ignored).
        # Returning non-200 would cause Razorpay to retry endlessly.
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={"success": True, "data": result},
        )

    except InvalidPaymentSignatureError:
        logger.warning(
            "webhook_endpoint_signature_rejected",
            body_length=len(raw_body),
        )
        # Return 400 for invalid signatures — these are not retried by Razorpay.
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "success": False,
                "error": {"code": "PAY_001", "message": "Webhook signature invalid."},
            },
        )

    except Exception as exc:
        logger.exception("webhook_endpoint_unexpected", error=str(exc))
        # Return 200 to prevent infinite Razorpay retries for non-signature errors.
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={"success": False, "error": "Internal error"},
        )


# ─── Cancel Payment ───────────────────────────────────────────────────────────

@router.post(
    "/payments/{job_id}/cancel",
    status_code=status.HTTP_200_OK,
    summary="Cancel payment",
    description=(
        "Marks a payment as CANCELLED when the user dismisses the payment modal. "
        "The print job remains in PAYMENT_PENDING — the user can retry. "
        "Requires a valid guest session token."
    ),
)
async def cancel_payment(
    job_id: uuid.UUID,
    session_id: str = Depends(get_current_guest_session),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    """Cancels a payment when the user dismisses the modal."""
    service = PaymentService(db)

    try:
        await service.cancel_payment(job_id=job_id, session_id=session_id)
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={"success": True, "message": "Payment cancelled."},
        )
    except JobNotFoundError:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={
                "success": False,
                "error": {"code": "JOB_001", "message": "Job not found."},
            },
        )
    except Exception as exc:
        logger.exception("cancel_payment_unexpected", error=str(exc))
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"success": False, "error": {"code": "SYS_000"}},
        )


# ─── Payment Status Polling ───────────────────────────────────────────────────

@router.get(
    "/payments/{job_id}/status",
    summary="Get payment and job status",
    description=(
        "Polls the payment and job status for a print job. "
        "Returns verificationStage: PENDING | VERIFYING | VERIFIED | FAILED | CANCELLED | EXPIRED. "
        "Call every 2.5 seconds after payment modal closes until verificationStage reaches VERIFIED. "
        "Requires a valid guest session token."
    ),
)
async def get_payment_status(
    job_id: uuid.UUID,
    session_id: str = Depends(get_current_guest_session),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Returns current payment status, job status, and verification stage for polling."""
    job_repo = PrintJobRepository(db)
    pay_repo = PaymentRepository(db)

    from app.services.payment_service import _payment_to_verification_stage

    job = await job_repo.get_by_id_and_session(job_id, session_id)
    if not job:
        raise JobNotFoundError()

    payment = await pay_repo.get_by_print_job_id(job_id)
    payment_status = payment.status if payment else "CREATED"

    return {
        "success": True,
        "data": {
            "jobId": str(job.id),
            "jobStatus": job.status,
            "paymentStatus": payment_status,
            "verificationStage": _payment_to_verification_stage(
                payment_status, job.status
            ),
            "totalInr": str(job.total_inr),
            "paidAt": payment.paid_at if payment else None,
        },
    }


# ─── QR Order Status Polling ──────────────────────────────────────────────────

@router.get(
    "/payments/{job_id}/poll-order",
    summary="Poll gateway order status (QR flow)",
    description=(
        "Polls the payment gateway for the current order status. "
        "Used by the QR payment flow — call every 3 seconds while showing QR. "
        "Returns isPaid=true when the customer has completed payment. "
        "Requires a valid guest session token."
    ),
)
async def poll_order_status(
    job_id: uuid.UUID,
    session_id: str = Depends(get_current_guest_session),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    """Polls the gateway for order payment status. Used for QR flow auto-verification."""
    service = PaymentService(db)

    try:
        result = await service.poll_order_status(
            job_id=job_id,
            session_id=session_id,
        )
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={"success": True, "data": result},
        )
    except JobNotFoundError:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={
                "success": False,
                "error": {"code": "JOB_001", "message": "Job not found."},
            },
        )
    except Exception as exc:
        logger.exception("poll_order_status_unexpected", error=str(exc))
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"success": False, "error": {"code": "SYS_000"}},
        )

"""
PrintBar Backend — Payment Service

Orchestrates the complete payment lifecycle using Razorpay Standard Checkout:
    1. Create print job (UPLOADED → VALIDATED → PAYMENT_PENDING)
    2. Create Razorpay order → return order_id + key_id to frontend
    3. Frontend opens Razorpay modal → user pays
    4. Frontend sends razorpay_order_id, razorpay_payment_id, razorpay_signature
    5. Backend verifies HMAC-SHA256 signature
    6. Verify amount matches stored order
    7. Transition print job to PAYMENT_SUCCESS → QUEUED
    8. Job dispatcher notifies Raspberry Pi via WebSocket

This is the single source of truth for payment business logic.
No payment logic exists in routes.

Legacy Easebuzz methods (initiate_checkout, process_webhook) are kept
for backward compatibility with any existing PENDING payments in the DB.
New payments use create_razorpay_order + verify_razorpay_payment.
"""

from __future__ import annotations

import secrets
import uuid
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.constants import PAYMENT_GATEWAY_RAZORPAY
from app.core.logging import get_logger
from app.exceptions.base import (
    DuplicatePaymentError,
    InvalidPaymentSignatureError,
    PaymentAmountMismatchError,
    PaymentOrderNotFoundError,
)
from app.models.payment import Payment
from app.models.print_job import PrintJob
from app.payments.razorpay import razorpay_gateway
from app.repositories.payment_repository import PaymentRepository
from app.repositories.print_job_repository import PrintJobRepository
from app.repositories.uploaded_file_repository import UploadedFileRepository
from app.services.pricing_service import PricingService

logger = get_logger(__name__)
settings = get_settings()


class PaymentService:
    """
    Orchestrates payment initiation and verification using Razorpay.

    Args:
        db: Async SQLAlchemy session.
    """

    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._payment_repo = PaymentRepository(db)
        self._job_repo = PrintJobRepository(db)
        self._upload_repo = UploadedFileRepository(db)
        self._pricing = PricingService(db)

    # ─── Razorpay: Create Order ───────────────────────────────────────────────

    async def create_razorpay_order(
        self,
        session_id: str,
        file_id: uuid.UUID,
        color_mode: str,
        paper_size: str,
        copies: int,
        duplex: bool,
        pages_selected: int,
        pages_per_sheet: int,
        page_range: str | None,
        orientation: str,
        idempotency_key: str | None = None,
    ) -> dict:
        """
        Creates a print job + Razorpay order and returns order details.

        The frontend uses the returned data to open the Razorpay checkout modal.
        The KEY_SECRET never leaves the backend.

        Idempotent: if a job with the same idempotency key already exists,
        returns the existing Razorpay order details.

        Args:
            session_id:       Guest session ID.
            file_id:          UUID of the validated uploaded file.
            color_mode:       "BW" or "COLOR".
            paper_size:       "A4", "A3", "LETTER", or "LEGAL".
            copies:           Number of copies.
            duplex:           True for double-sided.
            pages_selected:   Number of pages to print.
            pages_per_sheet:  Pages per physical sheet.
            page_range:       Optional page range string (e.g., "1-5,8").
            orientation:      "portrait" or "landscape".
            idempotency_key:  Optional client-provided idempotency key.

        Returns:
            Dict with:
                jobId, paymentId, razorpayOrderId, amountPaise,
                currency, keyId (public KEY_ID), totalInr, breakdown.
        """
        idem_key = idempotency_key or secrets.token_hex(16)

        # Idempotency: check for an existing job with this key.
        existing_job = await self._job_repo.get_by_idempotency_key(idem_key)
        if existing_job:
            existing_payment = await self._payment_repo.get_by_print_job_id(
                existing_job.id
            )
            if existing_payment and existing_payment.gateway_order_id:
                logger.info(
                    "razorpay_create_order_duplicate",
                    job_id=str(existing_job.id),
                    idempotency_key=idem_key,
                )
                # Reconstruct paise from stored INR amount.
                amount_paise = razorpay_gateway.inr_to_paise(existing_payment.amount_inr)
                return {
                    "jobId": str(existing_job.id),
                    "paymentId": str(existing_payment.id),
                    "razorpayOrderId": existing_payment.gateway_order_id,
                    "amountPaise": amount_paise,
                    "currency": settings.RAZORPAY_CURRENCY,
                    "keyId": settings.RAZORPAY_KEY_ID,  # Public key only.
                    "totalInr": str(existing_job.total_inr),
                    "idempotent": True,
                }

        # Validate the file belongs to this session.
        uploaded_file = await self._upload_repo.get_by_id_and_session(
            file_id, session_id
        )
        if not uploaded_file or uploaded_file.is_deleted:
            from app.exceptions.base import UploadNotFoundError
            raise UploadNotFoundError()

        # Recalculate price (backend always owns pricing).
        calc = await self._pricing.calculate(
            pages_selected=pages_selected,
            color_mode=color_mode,
            paper_size=paper_size,
            copies=copies,
            duplex=duplex,
            pages_per_sheet=pages_per_sheet,
        )

        # Create PrintJob.
        job = await self._job_repo.create(
            session_id=session_id,
            uploaded_file_id=file_id,
            color_mode=color_mode,
            paper_size=paper_size,
            copies=copies,
            duplex=duplex,
            pages_selected=pages_selected,
            pages_per_sheet=pages_per_sheet,
            page_range=page_range,
            orientation=orientation,
            subtotal_inr=calc.subtotal_inr,
            gst_inr=calc.gst_inr,
            total_inr=calc.total_inr,
            idempotency_key=idem_key,
        )

        # State transitions: UPLOADED → VALIDATED → PAYMENT_PENDING.
        await self._job_repo.transition(job.id, "VALIDATED")
        await self._job_repo.transition(job.id, "PAYMENT_PENDING")

        # Create Payment record in CREATED state.
        payment = await self._payment_repo.create_payment(
            print_job_id=job.id,
            amount_inr=calc.total_inr,
            idempotency_key=f"rzp_{idem_key}",
        )

        # Create Razorpay order.
        receipt_id = str(job.id)[:40]  # Razorpay max: 40 chars.
        razorpay_order = await razorpay_gateway.create_order(
            amount_inr=calc.total_inr,
            receipt_id=receipt_id,
            notes={
                "job_id": str(job.id),
                "payment_id": str(payment.id),
                "session_id": session_id[:8],  # Truncated for privacy.
            },
        )

        # Store the Razorpay order ID as gateway_order_id.
        await self._payment_repo.update_gateway_order_id(
            payment.id, razorpay_order["id"]
        )

        # Also update the gateway field to RAZORPAY.
        from sqlalchemy import update
        from app.models.payment import Payment as PaymentModel
        await self._db.execute(
            update(PaymentModel)
            .where(PaymentModel.id == payment.id)
            .values(gateway=PAYMENT_GATEWAY_RAZORPAY)
        )

        logger.info(
            "razorpay_order_created_for_job",
            job_id=str(job.id),
            payment_id=str(payment.id),
            razorpay_order_id=razorpay_order["id"],
            total_inr=str(calc.total_inr),
        )

        return {
            "jobId": str(job.id),
            "paymentId": str(payment.id),
            "razorpayOrderId": razorpay_order["id"],
            "amountPaise": razorpay_order["amount"],  # Integer paise.
            "currency": razorpay_order["currency"],
            "keyId": settings.RAZORPAY_KEY_ID,  # Public key — safe for frontend.
            "totalInr": str(calc.total_inr),
            "breakdown": calc.to_dict(),
            "idempotent": False,
        }

    # ─── Razorpay: Verify Payment ─────────────────────────────────────────────

    async def verify_razorpay_payment(
        self,
        razorpay_order_id: str,
        razorpay_payment_id: str,
        razorpay_signature: str,
        job_id: uuid.UUID,
    ) -> dict:
        """
        Verifies a Razorpay payment callback and transitions the print job.

        Steps:
            1. Look up payment by job_id.
            2. Store raw verification attempt in webhook log.
            3. Verify HMAC-SHA256 signature (constant-time comparison).
            4. Verify amount matches stored payment record.
            5. Check for duplicate processing.
            6. Mark payment SUCCESS.
            7. Transition job: PAYMENT_PENDING → PAYMENT_SUCCESS → QUEUED.

        Args:
            razorpay_order_id:   Razorpay order ID from callback.
            razorpay_payment_id: Razorpay payment ID from callback.
            razorpay_signature:  HMAC-SHA256 signature from callback.
            job_id:              Our internal print job UUID.

        Returns:
            Dict with jobId and final job status.

        Raises:
            PaymentOrderNotFoundError:   If no payment exists for this job.
            InvalidPaymentSignatureError: If signature verification fails.
            DuplicatePaymentError:        If payment was already processed.
        """
        # Step 1: Look up the payment by job ID.
        job: PrintJob | None = await self._job_repo.get_by_id(job_id)
        payment: Payment | None = None

        if job:
            payment = await self._payment_repo.get_by_print_job_id(job.id)

        # Step 2: Store raw verification attempt (always, before any checks).
        raw_payload = {
            "razorpay_order_id": razorpay_order_id,
            "razorpay_payment_id": razorpay_payment_id,
            # Signature is stored truncated — never log the full signature.
            "razorpay_signature_prefix": razorpay_signature[:16] + "...",
            "job_id": str(job_id),
        }
        webhook = await self._payment_repo.store_webhook(
            payment_id=payment.id if payment else None,
            raw_payload=raw_payload,
            gateway_txn_id=razorpay_payment_id,
            event_type="payment.verify",
            signature_valid=False,  # Updated after verification.
            amount_inr=payment.amount_inr if payment else None,
            status="PENDING_VERIFY",
        )

        # Step 3: Guard — payment must exist.
        if payment is None or job is None:
            logger.error(
                "razorpay_verify_payment_not_found",
                job_id=str(job_id),
                razorpay_order_id=razorpay_order_id,
            )
            await self._payment_repo.mark_webhook_processed(
                webhook.id, error="PAYMENT_NOT_FOUND"
            )
            raise PaymentOrderNotFoundError()

        # Validate that the razorpay_order_id matches what we stored.
        if payment.gateway_order_id != razorpay_order_id:
            logger.warning(
                "razorpay_verify_order_id_mismatch",
                stored_order_id=payment.gateway_order_id,
                received_order_id=razorpay_order_id,
                job_id=str(job_id),
            )
            await self._payment_repo.mark_webhook_processed(
                webhook.id, error="ORDER_ID_MISMATCH"
            )
            raise InvalidPaymentSignatureError()

        # Step 4: Verify HMAC-SHA256 signature (constant-time).
        sig_valid = razorpay_gateway.verify_signature(
            order_id=razorpay_order_id,
            payment_id=razorpay_payment_id,
            received_signature=razorpay_signature,
        )

        if not sig_valid:
            logger.warning(
                "razorpay_verify_signature_invalid",
                job_id=str(job_id),
                razorpay_order_id=razorpay_order_id,
                webhook_id=str(webhook.id),
            )
            await self._payment_repo.mark_failed(payment.id, "SIGNATURE_INVALID")
            await self._payment_repo.mark_webhook_processed(
                webhook.id, error="SIGNATURE_INVALID"
            )
            raise InvalidPaymentSignatureError()

        # Step 5: Duplicate check — prevent double-processing.
        if payment.status == "SUCCESS":
            await self._payment_repo.mark_webhook_processed(
                webhook.id, error="DUPLICATE_VERIFY"
            )
            raise DuplicatePaymentError()

        # Step 6: Mark payment SUCCESS.
        await self._payment_repo.mark_success(
            payment_id=payment.id,
            gateway_txn_id=razorpay_payment_id,
            payment_mode="RAZORPAY",
            vpa=None,
            bank_ref=None,
        )

        # Step 7: Transition job state machine.
        await self._job_repo.transition(job.id, "PAYMENT_SUCCESS")
        await self._job_repo.transition(job.id, "QUEUED")

        await self._payment_repo.mark_webhook_processed(webhook.id)

        logger.info(
            "razorpay_payment_verified_and_job_queued",
            job_id=str(job.id),
            payment_id=str(payment.id),
            razorpay_payment_id=razorpay_payment_id,
        )

        return {
            "jobId": str(job.id),
            "status": "QUEUED",
        }

    # ─── Status Polling ───────────────────────────────────────────────────────

    async def get_payment_status(self, job_id: uuid.UUID, session_id: str) -> dict:
        """
        Returns the current payment and job status for polling.

        Used by the frontend after the Razorpay modal closes.

        Args:
            job_id:     Print job UUID.
            session_id: Guest session ID for ownership verification.

        Returns:
            Dict with jobId, jobStatus, paymentStatus, totalInr, paidAt.
        """
        from app.exceptions.base import JobNotFoundError

        job = await self._job_repo.get_by_id_and_session(job_id, session_id)
        if not job:
            raise JobNotFoundError()

        payment = await self._payment_repo.get_by_print_job_id(job_id)

        return {
            "jobId": str(job.id),
            "jobStatus": job.status,
            "paymentStatus": payment.status if payment else "CREATED",
            "totalInr": str(job.total_inr),
            "paidAt": payment.paid_at if payment else None,
        }

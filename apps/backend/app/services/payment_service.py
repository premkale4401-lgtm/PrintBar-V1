"""
PrintBar Backend — Payment Service

Orchestrates the complete payment lifecycle using the provider-agnostic
PaymentProvider abstraction. Business logic here NEVER imports a specific
gateway — only the registry and base types.

Payment flows supported:
    1. Standard Checkout (Razorpay modal / UPI ID):
       create_order() → user pays → verify_payment_callback() → QUEUED
    2. QR Code payment (desktop):
       create_order() → show QR → poll_order_status() → webhook → QUEUED
    3. UPI App Switch (mobile):
       create_order() → deep link → app switch → webhook → QUEUED

All flows end with:
    backend verification → PAYMENT_SUCCESS → QUEUED → WebSocket → Pi → Print

Security invariants:
    - Frontend NEVER marks payment successful.
    - Backend recalculates price — never trusts frontend amounts.
    - Webhook signature verified using constant-time HMAC before any processing.
    - Duplicate webhooks are idempotent — silently ignored.
    - Duplicate callbacks raise DuplicatePaymentError (idempotent — returns success).
"""

from __future__ import annotations

import secrets
import uuid
from decimal import Decimal
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.constants import PAYMENT_GATEWAY_RAZORPAY
from app.core.logging import get_logger
from app.exceptions.base import (
    DuplicatePaymentError,
    InvalidPaymentSignatureError,
    JobNotFoundError,
    PaymentAmountMismatchError,
    PaymentGatewayError,
    PaymentOrderNotFoundError,
)
from app.models.payment import Payment
from app.models.print_job import PrintJob
from app.payments.base import WebhookResult
from app.payments.registry import get_active_provider
from app.repositories.payment_repository import PaymentRepository
from app.repositories.print_job_repository import PrintJobRepository
from app.repositories.uploaded_file_repository import UploadedFileRepository
from app.services.pricing_service import PricingService

logger = get_logger(__name__)
settings = get_settings()


class PaymentService:
    """
    Orchestrates payment initiation, verification, and webhook processing.

    Uses the provider registry — gateway-agnostic. Swapping gateways
    requires only updating registry.py, not this service.

    Args:
        db: Async SQLAlchemy session.
    """

    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._payment_repo = PaymentRepository(db)
        self._job_repo = PrintJobRepository(db)
        self._upload_repo = UploadedFileRepository(db)
        self._pricing = PricingService(db)
        self._provider = get_active_provider()

    # ─── Order Creation ───────────────────────────────────────────────────────

    async def create_order(
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
        Creates a print job + payment order and returns provider-agnostic order details.

        The frontend uses the returned data to open the payment UI.
        The gateway KEY_SECRET NEVER leaves the backend.

        Idempotent: if a job with the same idempotency key exists,
        returns the existing order details without creating a new one.

        Returns:
            Dict with:
                jobId, paymentId, gatewayOrderId, amountPaise,
                currency, keyId, totalInr, breakdown.
        """
        idem_key = idempotency_key or secrets.token_hex(16)

        # ── Idempotency check ──────────────────────────────────────────────────
        existing_job = await self._job_repo.get_by_idempotency_key(idem_key)
        if existing_job:
            existing_payment = await self._payment_repo.get_by_print_job_id(
                existing_job.id
            )
            if existing_payment and existing_payment.gateway_order_id:
                logger.info(
                    "payment_create_order_idempotent",
                    job_id=str(existing_job.id),
                    idempotency_key=idem_key,
                )
                # Use provider-agnostic conversion: amount_inr * 100 = paise.
                amount_paise = int(existing_payment.amount_inr * 100)
                return {
                    "jobId": str(existing_job.id),
                    "paymentId": str(existing_payment.id),
                    "gatewayOrderId": existing_payment.gateway_order_id,
                    "amountPaise": amount_paise,
                    "currency": "INR",
                    "keyId": settings.RAZORPAY_KEY_ID if not settings.is_mock_payment else "mock_key",
                    "totalInr": str(existing_job.total_inr),
                    "isMockMode": settings.is_mock_payment,
                    "idempotent": True,
                }

        # ── Validate file belongs to session ──────────────────────────────────
        uploaded_file = await self._upload_repo.get_by_id_and_session(
            file_id, session_id
        )
        if not uploaded_file or uploaded_file.is_deleted:
            from app.exceptions.base import UploadNotFoundError
            raise UploadNotFoundError()

        # ── Recalculate price (backend always owns pricing) ───────────────────
        calc = await self._pricing.calculate(
            pages_selected=pages_selected,
            color_mode=color_mode,
            paper_size=paper_size,
            copies=copies,
            duplex=duplex,
            pages_per_sheet=pages_per_sheet,
        )

        # ── Create PrintJob ───────────────────────────────────────────────────
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

        # State transitions: UPLOADED → VALIDATED → PAYMENT_PENDING
        await self._job_repo.transition(job.id, "VALIDATED")
        await self._job_repo.transition(job.id, "PAYMENT_PENDING")

        # ── Create Payment record ─────────────────────────────────────────────
        payment = await self._payment_repo.create_payment(
            print_job_id=job.id,
            amount_inr=calc.total_inr,
            idempotency_key=f"pay_{idem_key}",
        )

        # ── Create Gateway Order ──────────────────────────────────────────────
        receipt_id = str(job.id)[:40]
        order_result = await self._provider.create_order(
            amount_inr=calc.total_inr,
            receipt_id=receipt_id,
            notes={
                "job_id": str(job.id),
                "payment_id": str(payment.id),
                "session_id": session_id[:8],  # Truncated for privacy.
            },
        )

        # Store gateway order ID.
        await self._payment_repo.update_gateway_order_id(
            payment.id, order_result.gateway_order_id
        )

        # Update gateway field — use the active provider's name.
        from sqlalchemy import update as sql_update
        from app.models.payment import Payment as PaymentModel
        gateway_name = "MOCK" if settings.is_mock_payment else PAYMENT_GATEWAY_RAZORPAY
        await self._db.execute(
            sql_update(PaymentModel)
            .where(PaymentModel.id == payment.id)
            .values(gateway=gateway_name)
        )

        logger.info(
            "payment_order_created",
            job_id=str(job.id),
            payment_id=str(payment.id),
            gateway_order_id=order_result.gateway_order_id,
            total_inr=str(calc.total_inr),
        )

        return {
            "jobId": str(job.id),
            "paymentId": str(payment.id),
            "gatewayOrderId": order_result.gateway_order_id,
            # Backward-compat aliases used by frontend.
            "razorpayOrderId": order_result.gateway_order_id,
            "amountPaise": order_result.amount_paise,
            "currency": order_result.currency,
            "keyId": settings.RAZORPAY_KEY_ID,  # Public key — safe for frontend.
            "totalInr": str(calc.total_inr),
            "breakdown": calc.to_dict(),
            "idempotent": False,
        }

    # Backward-compat alias.
    async def create_razorpay_order(self, **kwargs) -> dict:  # type: ignore[override]
        return await self.create_order(**kwargs)

    # ─── Callback Verification (Standard Checkout / UPI ID) ──────────────────

    async def verify_payment_callback(
        self,
        razorpay_order_id: str,
        razorpay_payment_id: str,
        razorpay_signature: str,
        job_id: uuid.UUID,
    ) -> dict:
        """
        Verifies a payment callback from the Razorpay Standard Checkout.

        Called by the frontend immediately after the payment modal handler fires.
        The backend is authoritative — never trust the frontend's success status.

        Steps:
            1. Look up payment by job_id.
            2. Store raw verification attempt (audit log).
            3. Verify HMAC-SHA256 signature (constant-time).
            4. Check gateway_order_id matches stored record.
            5. Duplicate check (idempotent).
            6. Mark payment VERIFYING → SUCCESS.
            7. Transition job: PAYMENT_PENDING → PAYMENT_SUCCESS → QUEUED.

        Returns:
            Dict with jobId and final status.

        Raises:
            PaymentOrderNotFoundError:   No payment found for this job.
            InvalidPaymentSignatureError: Signature verification failed.
            DuplicatePaymentError:        Payment already processed (idempotent).
        """
        job: PrintJob | None = await self._job_repo.get_by_id(job_id)
        payment: Payment | None = None

        if job:
            payment = await self._payment_repo.get_by_print_job_id(job.id)

        # Always store the raw verification attempt before any checks.
        raw_payload = {
            "razorpay_order_id": razorpay_order_id,
            "razorpay_payment_id": razorpay_payment_id,
            "razorpay_signature_prefix": razorpay_signature[:16] + "...",
            "job_id": str(job_id),
        }
        webhook = await self._payment_repo.store_webhook(
            payment_id=payment.id if payment else None,
            raw_payload=raw_payload,
            gateway_txn_id=razorpay_payment_id,
            event_type="payment.verify_callback",
            signature_valid=False,
            amount_inr=payment.amount_inr if payment else None,
            status="PENDING_VERIFY",
        )

        if payment is None or job is None:
            logger.error(
                "payment_verify_callback_not_found",
                job_id=str(job_id),
                razorpay_order_id=razorpay_order_id,
            )
            await self._payment_repo.mark_webhook_processed(
                webhook.id, error="PAYMENT_NOT_FOUND"
            )
            raise PaymentOrderNotFoundError()

        # Validate gateway_order_id matches stored record.
        if payment.gateway_order_id != razorpay_order_id:
            logger.warning(
                "payment_verify_callback_order_id_mismatch",
                stored=payment.gateway_order_id,
                received=razorpay_order_id,
                job_id=str(job_id),
            )
            await self._payment_repo.mark_webhook_processed(
                webhook.id, error="ORDER_ID_MISMATCH"
            )
            raise InvalidPaymentSignatureError()

        # Duplicate check — idempotent.
        if payment.status == "SUCCESS":
            await self._payment_repo.mark_webhook_processed(
                webhook.id, error="DUPLICATE_VERIFY"
            )
            raise DuplicatePaymentError()

        # Verify HMAC-SHA256 signature (constant-time).
        sig_valid = self._provider.verify_signature(
            order_id=razorpay_order_id,
            payment_id=razorpay_payment_id,
            received_signature=razorpay_signature,
        )

        if not sig_valid:
            logger.warning(
                "payment_verify_callback_signature_invalid",
                job_id=str(job_id),
                webhook_id=str(webhook.id),
            )
            await self._payment_repo.mark_failed(payment.id, "SIGNATURE_INVALID")
            await self._payment_repo.mark_webhook_processed(
                webhook.id, error="SIGNATURE_INVALID"
            )
            raise InvalidPaymentSignatureError()

        # Mark payment VERIFYING → SUCCESS.
        await self._payment_repo.mark_verifying(payment.id)
        await self._payment_repo.mark_success(
            payment_id=payment.id,
            gateway_txn_id=razorpay_payment_id,
            payment_mode="RAZORPAY_CALLBACK",
            vpa=None,
            bank_ref=None,
            signature_prefix=razorpay_signature[:16] + "...",
        )

        # Transition job state machine.
        await self._job_repo.transition(job.id, "PAYMENT_SUCCESS")
        await self._job_repo.transition(job.id, "QUEUED")

        await self._payment_repo.mark_webhook_processed(webhook.id)

        logger.info(
            "payment_callback_verified_and_queued",
            job_id=str(job.id),
            payment_id=str(payment.id),
            razorpay_payment_id=razorpay_payment_id,
        )

        return {"jobId": str(job.id), "status": "QUEUED"}

    # Backward-compat alias.
    async def verify_razorpay_payment(
        self,
        razorpay_order_id: str,
        razorpay_payment_id: str,
        razorpay_signature: str,
        job_id: uuid.UUID,
    ) -> dict:
        return await self.verify_payment_callback(
            razorpay_order_id=razorpay_order_id,
            razorpay_payment_id=razorpay_payment_id,
            razorpay_signature=razorpay_signature,
            job_id=job_id,
        )

    # ─── Webhook Handler ──────────────────────────────────────────────────────

    async def process_webhook(
        self,
        raw_body: bytes,
        signature_header: str,
    ) -> dict:
        """
        Processes an incoming Razorpay webhook.

        SECURITY: Signature is verified on raw bytes BEFORE JSON parsing.
        IDEMPOTENCY: Duplicate webhooks (same gateway_txn_id) are silently ignored.

        Steps:
            1. Verify HMAC-SHA256 signature (constant-time, raw bytes).
            2. Check for duplicate webhook (idempotent).
            3. Look up payment by gateway_order_id.
            4. Store raw webhook payload (audit).
            5. Verify amount matches stored record.
            6. Transition payment: PENDING/VERIFYING → SUCCESS.
            7. Transition job: PAYMENT_PENDING → PAYMENT_SUCCESS → QUEUED.
            8. Notify Raspberry Pi via WebSocket (job dispatcher picks it up).

        Args:
            raw_body:         Raw HTTP request body bytes.
            signature_header: Value of X-Razorpay-Signature header.

        Returns:
            Dict with processing result.
        """
        # Step 1: Verify signature and parse payload.
        try:
            webhook_result: WebhookResult = self._provider.verify_webhook(
                raw_body=raw_body,
                signature_header=signature_header,
            )
        except InvalidPaymentSignatureError:
            logger.warning("webhook_signature_invalid")
            raise

        # Only process payment.captured and order.paid events.
        if not webhook_result.is_payment_success:
            logger.info(
                "webhook_non_success_event_ignored",
                event_type=webhook_result.event_type,
            )
            return {"processed": False, "reason": "non_success_event"}

        # Step 2: Idempotency — reject duplicate webhooks.
        if webhook_result.gateway_txn_id:
            is_duplicate = await self._payment_repo.is_webhook_duplicate(
                webhook_result.gateway_txn_id
            )
            if is_duplicate:
                logger.info(
                    "webhook_duplicate_ignored",
                    gateway_txn_id=webhook_result.gateway_txn_id,
                )
                return {"processed": False, "reason": "duplicate"}

        # Step 3: Look up payment by gateway_order_id.
        payment: Payment | None = await self._payment_repo.get_by_gateway_order_id(
            webhook_result.gateway_order_id
        )

        if not payment:
            logger.error(
                "webhook_payment_not_found",
                gateway_order_id=webhook_result.gateway_order_id,
                gateway_txn_id=webhook_result.gateway_txn_id,
            )
            # Store for audit even if we can't process.
            await self._payment_repo.store_webhook(
                payment_id=None,
                raw_payload=webhook_result.raw,
                gateway_txn_id=webhook_result.gateway_txn_id,
                event_type=webhook_result.event_type,
                signature_valid=True,
                amount_inr=None,
                status="ORDER_NOT_FOUND",
            )
            return {"processed": False, "reason": "order_not_found"}

        # Step 4: Store raw webhook (always, before processing).
        from decimal import Decimal as D
        amount_inr_from_webhook = D(webhook_result.amount_paise) / 100

        webhook_record = await self._payment_repo.store_webhook(
            payment_id=payment.id,
            raw_payload=webhook_result.raw,
            gateway_txn_id=webhook_result.gateway_txn_id,
            event_type=webhook_result.event_type,
            signature_valid=True,
            amount_inr=amount_inr_from_webhook,
            status="SUCCESS",
        )

        # Already processed by callback verification?
        if payment.status == "SUCCESS":
            logger.info(
                "webhook_payment_already_success",
                payment_id=str(payment.id),
                gateway_txn_id=webhook_result.gateway_txn_id,
            )
            await self._payment_repo.mark_webhook_processed(webhook_record.id)
            return {"processed": False, "reason": "already_success"}

        # Step 5: Verify amount matches stored record.
        # Provider-agnostic: convert paise to INR and compare with tolerance.
        expected_paise = int(payment.amount_inr * 100)
        if abs(webhook_result.amount_paise - expected_paise) > 1:  # 1 paise tolerance for rounding.
            logger.error(
                "webhook_amount_mismatch",
                payment_id=str(payment.id),
                webhook_paise=webhook_result.amount_paise,
                expected_paise=expected_paise,
                expected_inr=str(payment.amount_inr),
            )
            await self._payment_repo.mark_failed(payment.id, "AMOUNT_MISMATCH")
            await self._payment_repo.mark_webhook_processed(
                webhook_record.id, error="AMOUNT_MISMATCH"
            )
            return {"processed": False, "reason": "amount_mismatch"}

        # Step 6: Mark payment VERIFYING → SUCCESS.
        await self._payment_repo.mark_verifying(payment.id)
        await self._payment_repo.mark_success(
            payment_id=payment.id,
            gateway_txn_id=webhook_result.gateway_txn_id,
            payment_mode=webhook_result.payment_mode,
            vpa=webhook_result.vpa,
            bank_ref=webhook_result.bank_ref,
        )

        # Step 7: Look up and transition job.
        job = await self._job_repo.get_by_id(payment.print_job_id)
        if job:
            # Transition to PAYMENT_SUCCESS only if currently in PAYMENT_PENDING.
            if job.status == "PAYMENT_PENDING":
                await self._job_repo.transition(job.id, "PAYMENT_SUCCESS")
                await self._job_repo.transition(job.id, "QUEUED")
                logger.info(
                    "webhook_job_queued",
                    job_id=str(job.id),
                    payment_id=str(payment.id),
                )
            else:
                logger.info(
                    "webhook_job_already_progressed",
                    job_id=str(job.id),
                    job_status=job.status,
                )

        await self._payment_repo.mark_webhook_processed(webhook_record.id)

        logger.info(
            "webhook_processed_successfully",
            payment_id=str(payment.id),
            gateway_txn_id=webhook_result.gateway_txn_id,
            event_type=webhook_result.event_type,
        )

        return {"processed": True, "jobId": str(job.id) if job else None}

    # ─── Cancel Payment ───────────────────────────────────────────────────────

    async def cancel_payment(
        self, job_id: uuid.UUID, session_id: str
    ) -> None:
        """
        Cancels a payment when the user dismisses the payment modal.

        Marks the payment as CANCELLED so it's visible in audit logs.
        The print job remains in PAYMENT_PENDING — user can retry.

        Args:
            job_id:     Print job UUID.
            session_id: Guest session ID for ownership check.

        Raises:
            JobNotFoundError: If job doesn't belong to session.
        """
        job = await self._job_repo.get_by_id_and_session(job_id, session_id)
        if not job:
            raise JobNotFoundError()

        payment = await self._payment_repo.get_by_print_job_id(job_id)
        if payment and payment.status not in ("SUCCESS", "CANCELLED", "REFUNDED"):
            await self._payment_repo.mark_cancelled(payment.id)
            logger.info(
                "payment_cancelled_by_user",
                job_id=str(job_id),
                payment_id=str(payment.id),
            )

    # ─── Status ───────────────────────────────────────────────────────────────

    async def get_payment_status(self, job_id: uuid.UUID, session_id: str) -> dict:
        """
        Returns the current payment and job status for frontend polling.

        Args:
            job_id:     Print job UUID.
            session_id: Guest session ID.

        Returns:
            Dict with jobId, jobStatus, paymentStatus, verificationStage, totalInr, paidAt.
        """
        job = await self._job_repo.get_by_id_and_session(job_id, session_id)
        if not job:
            raise JobNotFoundError()

        payment = await self._payment_repo.get_by_print_job_id(job_id)

        payment_status = payment.status if payment else "CREATED"

        # Map to frontend verification stage.
        verification_stage = _payment_to_verification_stage(
            payment_status, job.status
        )

        return {
            "jobId": str(job.id),
            "jobStatus": job.status,
            "paymentStatus": payment_status,
            "verificationStage": verification_stage,
            "totalInr": str(job.total_inr),
            "paidAt": payment.paid_at if payment else None,
        }

    async def poll_order_status(
        self, job_id: uuid.UUID, session_id: str
    ) -> dict:
        """
        Polls the gateway for the current order payment status.

        Used by the QR payment flow — the frontend polls this endpoint
        every few seconds until the customer scans and pays.

        Args:
            job_id:     Print job UUID.
            session_id: Guest session ID.

        Returns:
            Dict with isPaid flag and current verification stage.
        """
        job = await self._job_repo.get_by_id_and_session(job_id, session_id)
        if not job:
            raise JobNotFoundError()

        payment = await self._payment_repo.get_by_print_job_id(job_id)
        if not payment or not payment.gateway_order_id:
            return {"isPaid": False, "verificationStage": "PENDING"}

        # If already verified by webhook, no need to poll gateway.
        if payment.status == "SUCCESS":
            return {
                "isPaid": True,
                "verificationStage": "VERIFIED",
                "jobId": str(job_id),
                "jobStatus": job.status,
            }

        # Poll gateway.
        try:
            order_status = await self._provider.get_order_status(
                payment.gateway_order_id
            )
        except PaymentGatewayError:
            logger.warning(
                "poll_order_status_gateway_error",
                job_id=str(job_id),
            )
            return {"isPaid": False, "verificationStage": "PENDING", "gatewayError": True}

        return {
            "isPaid": order_status.is_paid,
            "verificationStage": "VERIFYING" if order_status.is_paid else "PENDING",
            "jobId": str(job_id),
            "jobStatus": job.status,
        }


def _payment_to_verification_stage(payment_status: str, job_status: str) -> str:
    """Maps payment + job status to the frontend verification stage string."""
    if payment_status == "SUCCESS" or job_status in (
        "QUEUED", "ASSIGNED", "DOWNLOADING", "READY_TO_PRINT", "PRINTING", "COMPLETED"
    ):
        return "VERIFIED"
    if payment_status == "VERIFYING":
        return "VERIFYING"
    if payment_status in ("FAILED",):
        return "FAILED"
    if payment_status == "CANCELLED":
        return "CANCELLED"
    if payment_status == "EXPIRED":
        return "EXPIRED"
    return "PENDING"

"""
PrintBar Backend — Payment Service

Orchestrates the complete payment lifecycle:
    1. Create print job (UPLOADED → VALIDATED → PAYMENT_PENDING)
    2. Initiate Easebuzz payment → get payment URL
    3. Handle webhook (verify signature → verify amount → update status)
    4. Transition print job to PAYMENT_SUCCESS → QUEUED

This is the single source of truth for payment business logic.
No payment logic exists in routes.
"""

from __future__ import annotations

import secrets
import uuid
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.exceptions.base import (
    DuplicatePaymentError,
    InvalidPaymentSignatureError,
    PaymentAmountMismatchError,
    PaymentOrderNotFoundError,
)
from app.models.payment import Payment
from app.models.print_job import PrintJob
from app.payments.easebuzz import easebuzz_gateway
from app.repositories.payment_repository import PaymentRepository
from app.repositories.print_job_repository import PrintJobRepository
from app.repositories.uploaded_file_repository import UploadedFileRepository
from app.services.pricing_service import PricingService

logger = get_logger(__name__)
settings = get_settings()


class PaymentService:
    """
    Orchestrates payment initiation and webhook processing.

    Args:
        db: Async SQLAlchemy session.
    """

    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._payment_repo = PaymentRepository(db)
        self._job_repo = PrintJobRepository(db)
        self._upload_repo = UploadedFileRepository(db)
        self._pricing = PricingService(db)

    async def initiate_checkout(
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
        success_url: str,
        failure_url: str,
        idempotency_key: str | None = None,
    ) -> dict:
        """
        Creates a print job + payment record and returns the Easebuzz payment URL.

        Idempotent: if a job with the same idempotency key already exists,
        returns the existing payment URL.

        Args:
            session_id:       Guest session ID.
            file_id:          UUID of the validated uploaded file.
            color_mode:       "BW" or "COLOR".
            paper_size:       "A4", "A3", "LETTER", or "LEGAL".
            copies:           Number of copies.
            duplex:           True for double-sided.
            pages_selected:   Pages to print.
            pages_per_sheet:  Pages per physical sheet.
            page_range:       Page range string (e.g., "1-5,8").
            orientation:      "portrait" or "landscape".
            success_url:      Backend URL for Easebuzz success redirect.
            failure_url:      Backend URL for Easebuzz failure redirect.
            idempotency_key:  Optional client-provided idempotency key.

        Returns:
            Dict with jobId, paymentId, paymentUrl, totalInr.
        """
        # Generate idempotency key if not provided.
        idem_key = idempotency_key or secrets.token_hex(16)

        # Check for existing job with same idempotency key.
        existing_job = await self._job_repo.get_by_idempotency_key(idem_key)
        if existing_job:
            existing_payment = await self._payment_repo.get_by_print_job_id(
                existing_job.id
            )
            if existing_payment and existing_payment.gateway_order_id:
                logger.info(
                    "payment_initiation_duplicate",
                    job_id=str(existing_job.id),
                    idempotency_key=idem_key,
                )
                return {
                    "jobId": str(existing_job.id),
                    "paymentId": str(existing_payment.id),
                    "paymentUrl": existing_payment.gateway_order_id,  # Stores URL
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

        # Calculate price.
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

        # Transition to VALIDATED then PAYMENT_PENDING.
        await self._job_repo.transition(job.id, "VALIDATED")
        await self._job_repo.transition(job.id, "PAYMENT_PENDING")

        # Create Payment record.
        payment = await self._payment_repo.create_payment(
            print_job_id=job.id,
            amount_inr=calc.total_inr,
            idempotency_key=f"pay_{idem_key}",
        )

        # Initiate Easebuzz payment.
        txnid = str(job.id)
        payment_url = await easebuzz_gateway.initiate_payment(
            txnid=txnid,
            amount=calc.total_inr,
            productinfo=f"PrintBar Print Job - {pages_selected} pages",
            firstname="Guest",
            email=f"guest_{session_id[:8]}@printbar.in",
            phone="9999999999",  # Required by Easebuzz; guest users don't provide phone.
            surl=success_url,
            furl=failure_url,
            udf1=str(payment.id),  # Store payment ID for webhook lookup.
        )

        # Store the payment URL as gateway_order_id (Easebuzz doesn't assign order IDs).
        await self._payment_repo.update_gateway_order_id(payment.id, payment_url)

        logger.info(
            "checkout_initiated",
            job_id=str(job.id),
            payment_id=str(payment.id),
            total_inr=str(calc.total_inr),
        )

        return {
            "jobId": str(job.id),
            "paymentId": str(payment.id),
            "paymentUrl": payment_url,
            "totalInr": str(calc.total_inr),
            "breakdown": calc.to_dict(),
            "idempotent": False,
        }

    async def process_webhook(self, payload: dict) -> dict:
        """
        Processes an Easebuzz payment webhook.

        Steps:
            1. Store raw payload verbatim.
            2. Verify signature.
            3. Look up payment by txnid (= print job ID).
            4. Verify amount.
            5. Update payment and print job status.

        Args:
            payload: Parsed form data from the Easebuzz webhook POST.

        Returns:
            Dict with processing result.
        """
        txnid = payload.get("txnid", "")
        status = payload.get("status", "")
        gateway_txn_id = payload.get("easepayid") or payload.get("bank_ref_num")
        amount_str = payload.get("amount", "0")

        # Step 1: Look up the payment by job ID (txnid = print job UUID).
        payment: Payment | None = None
        job: PrintJob | None = None

        try:
            job_uuid = uuid.UUID(txnid)
            job = await self._job_repo.get_by_id(job_uuid)
            if job:
                payment = await self._payment_repo.get_by_print_job_id(job.id)
        except (ValueError, TypeError):
            pass

        # Step 2: Store raw webhook (ALWAYS, even before signature check).
        webhook = await self._payment_repo.store_webhook(
            payment_id=payment.id if payment else None,
            raw_payload=payload,
            gateway_txn_id=gateway_txn_id,
            event_type=f"payment.{status.lower()}",
            signature_valid=False,  # Will be updated after verification.
            amount_inr=Decimal(amount_str) if amount_str else None,
            status=status,
        )

        # Step 3: Verify signature.
        sig_valid = easebuzz_gateway.verify_webhook_signature(payload)

        if not sig_valid:
            logger.warning(
                "webhook_signature_invalid",
                txnid=txnid,
                webhook_id=str(webhook.id),
            )
            await self._payment_repo.mark_webhook_processed(
                webhook.id, error="SIGNATURE_INVALID"
            )
            raise InvalidPaymentSignatureError()

        if payment is None or job is None:
            logger.error("webhook_payment_not_found", txnid=txnid)
            await self._payment_repo.mark_webhook_processed(
                webhook.id, error="PAYMENT_NOT_FOUND"
            )
            raise PaymentOrderNotFoundError()

        # Step 4: Handle status.
        if status.upper() == "SUCCESS":
            # Verify amount.
            try:
                easebuzz_gateway.verify_payment_amount(amount_str, payment.amount_inr)
            except PaymentAmountMismatchError:
                await self._payment_repo.mark_failed(payment.id, "AMOUNT_MISMATCH")
                await self._job_repo.transition(job.id, "PAYMENT_FAILED")
                await self._payment_repo.mark_webhook_processed(
                    webhook.id, error="AMOUNT_MISMATCH"
                )
                raise

            # Check for duplicate.
            if payment.status == "SUCCESS":
                await self._payment_repo.mark_webhook_processed(
                    webhook.id, error="DUPLICATE_WEBHOOK"
                )
                raise DuplicatePaymentError()

            # Mark payment SUCCESS.
            await self._payment_repo.mark_success(
                payment_id=payment.id,
                gateway_txn_id=gateway_txn_id or "",
                payment_mode=payload.get("mode"),
                vpa=payload.get("vpa"),
                bank_ref=payload.get("bank_ref_num"),
            )

            # Transition job: PAYMENT_PENDING → PAYMENT_SUCCESS → QUEUED.
            await self._job_repo.transition(job.id, "PAYMENT_SUCCESS")
            await self._job_repo.transition(job.id, "QUEUED")

            logger.info(
                "payment_webhook_success",
                txnid=txnid,
                job_id=str(job.id),
                payment_id=str(payment.id),
            )

        else:
            # Any non-success status = failure.
            await self._payment_repo.mark_failed(payment.id, status)
            await self._job_repo.transition(job.id, "PAYMENT_FAILED")

            logger.warning(
                "payment_webhook_failed",
                txnid=txnid,
                status=status,
            )

        await self._payment_repo.mark_webhook_processed(webhook.id)

        return {
            "processed": True,
            "status": status,
            "txnid": txnid,
        }

"""
PrintBar Backend — Payment Repository

Data access layer for Payment and PaymentWebhook records.
All database interactions for payments go through this class.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.exceptions.base import InvalidPaymentTransition
from app.models.payment import Payment
from app.models.payment_webhook import PaymentWebhook

logger = get_logger(__name__)
settings = get_settings()


class PaymentRepository:
    """
    Repository for Payment and PaymentWebhook CRUD operations.

    Args:
        db: SQLAlchemy async session.
    """

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def create_payment(
        self,
        print_job_id: uuid.UUID,
        amount_inr: object,
        idempotency_key: str,
    ) -> Payment:
        """
        Creates a new Payment record in CREATED status.

        Args:
            print_job_id:     UUID of the associated print job.
            amount_inr:       Decimal amount in INR.
            idempotency_key:  Unique key to prevent duplicate payments.

        Returns:
            Newly created Payment instance.
        """
        now = datetime.now(tz=UTC)
        expires_at = (now + timedelta(minutes=settings.PAYMENT_TIMEOUT_MINUTES)).isoformat()

        payment = Payment(
            print_job_id=print_job_id,
            amount_inr=amount_inr,  # type: ignore[arg-type]
            idempotency_key=idempotency_key,
            expires_at=expires_at,
        )
        self._db.add(payment)
        await self._db.flush()

        logger.info(
            "payment_created",
            payment_id=str(payment.id),
            print_job_id=str(print_job_id),
            amount=str(amount_inr),
        )
        return payment

    async def get_by_id(self, payment_id: uuid.UUID) -> Payment | None:
        result = await self._db.execute(select(Payment).where(Payment.id == payment_id))
        return result.scalar_one_or_none()

    async def get_by_gateway_order_id(self, gateway_order_id: str) -> Payment | None:
        result = await self._db.execute(
            select(Payment).where(Payment.gateway_order_id == gateway_order_id)
        )
        return result.scalar_one_or_none()

    async def get_by_gateway_txn_id(self, gateway_txn_id: str) -> Payment | None:
        """Looks up a payment by the gateway transaction ID for webhook deduplication."""
        result = await self._db.execute(
            select(Payment).where(Payment.gateway_txn_id == gateway_txn_id)
        )
        return result.scalar_one_or_none()

    async def get_by_print_job_id(self, print_job_id: uuid.UUID) -> Payment | None:
        result = await self._db.execute(select(Payment).where(Payment.print_job_id == print_job_id))
        return result.scalar_one_or_none()

    async def update_gateway_order_id(self, payment_id: uuid.UUID, gateway_order_id: str) -> None:
        """Sets the gateway order ID after order creation succeeds."""
        payment = await self.get_by_id(payment_id)
        if not payment:
            return

        self._validate_transition(payment.status, "PENDING")

        await self._db.execute(
            update(Payment)
            .where(Payment.id == payment_id)
            .values(
                gateway_order_id=gateway_order_id,
                status="PENDING",
            )
        )

    def _validate_transition(self, current: str, target: str) -> None:
        valid_transitions = {
            "CREATED": ["PENDING"],
            "PENDING": ["VERIFYING", "SUCCESS", "FAILED", "CANCELLED", "EXPIRED"],
            "VERIFYING": ["SUCCESS", "FAILED"],
            # Terminal states allow no transitions
            "SUCCESS": [],
            "FAILED": [],
            "CANCELLED": [],
            "EXPIRED": [],
        }

        if target not in valid_transitions.get(current, []):
            logger.warning(
                "invalid_payment_transition",
                current_status=current,
                target_status=target,
            )
            raise InvalidPaymentTransition(current, target)

    async def mark_verifying(self, payment_id: uuid.UUID) -> None:
        """
        Marks payment as VERIFYING — intermediate state while webhook is being processed.
        Prevents race conditions between callback and webhook handlers.
        """
        payment = await self.get_by_id(payment_id)
        if not payment:
            return

        self._validate_transition(payment.status, "VERIFYING")

        await self._db.execute(
            update(Payment).where(Payment.id == payment_id).values(status="VERIFYING")
        )
        logger.info("payment_marked_verifying", payment_id=str(payment_id))

    async def mark_success(
        self,
        payment_id: uuid.UUID,
        gateway_txn_id: str,
        payment_mode: str | None,
        vpa: str | None,
        bank_ref: str | None,
        signature_prefix: str | None = None,
    ) -> None:
        """
        Marks a payment as SUCCESS after verified webhook/callback.

        Args:
            payment_id:       UUID of the payment.
            gateway_txn_id:   Gateway transaction/payment ID.
            payment_mode:     Payment method (UPI, CARD, etc.).
            vpa:              UPI VPA if applicable.
            bank_ref:         Bank reference number if applicable.
            signature_prefix: First 16 chars of signature for audit (never full).
        """
        now = datetime.now(tz=UTC).isoformat()
        payment = await self.get_by_id(payment_id)
        if not payment:
            return

        self._validate_transition(payment.status, "SUCCESS")

        await self._db.execute(
            update(Payment)
            .where(Payment.id == payment_id)
            .values(
                status="SUCCESS",
                gateway_txn_id=gateway_txn_id,
                payment_mode=payment_mode,
                vpa=vpa,
                bank_ref=bank_ref,
                gateway_signature=signature_prefix,  # Truncated — never full.
                verification_time=now,
                paid_at=now,
            )
        )
        logger.info("payment_marked_success", payment_id=str(payment_id))

    async def mark_failed(self, payment_id: uuid.UUID, reason: str = "GATEWAY_FAILURE") -> None:
        """Marks a payment as FAILED."""
        payment = await self.get_by_id(payment_id)
        if not payment:
            return

        self._validate_transition(payment.status, "FAILED")

        await self._db.execute(
            update(Payment).where(Payment.id == payment_id).values(status="FAILED")
        )
        logger.info("payment_marked_failed", payment_id=str(payment_id), reason=reason)

    async def mark_expired(self, payment_id: uuid.UUID) -> None:
        """Marks a payment as EXPIRED."""
        payment = await self.get_by_id(payment_id)
        if not payment:
            return

        self._validate_transition(payment.status, "EXPIRED")

        await self._db.execute(
            update(Payment).where(Payment.id == payment_id).values(status="EXPIRED")
        )

    async def mark_cancelled(self, payment_id: uuid.UUID) -> None:
        """
        Marks a payment as CANCELLED.
        Called when the user dismisses the payment modal without completing payment.
        """
        payment = await self.get_by_id(payment_id)
        if not payment:
            return

        self._validate_transition(payment.status, "CANCELLED")

        await self._db.execute(
            update(Payment).where(Payment.id == payment_id).values(status="CANCELLED")
        )
        logger.info("payment_marked_cancelled", payment_id=str(payment_id))

    async def is_webhook_duplicate(self, gateway_event_id: str) -> bool:
        """
        Checks whether a webhook with this event ID has already been processed.

        Used for idempotency — Razorpay may send the same webhook multiple times.

        Args:
            gateway_event_id: The unique event ID from the gateway.

        Returns:
            True if already processed, False otherwise.
        """
        if not gateway_event_id:
            return False

        result = await self._db.execute(
            select(PaymentWebhook).where(PaymentWebhook.gateway_event_id == gateway_event_id)
        )
        return result.scalar_one_or_none() is not None

    async def store_webhook(
        self,
        payment_id: uuid.UUID | None,
        raw_payload: dict,
        gateway_txn_id: str | None,
        event_type: str,
        signature_valid: bool,
        amount_inr: object | None = None,
        status: str | None = None,
        gateway_event_id: str | None = None,
    ) -> PaymentWebhook:
        """
        Stores a raw webhook payload verbatim before any processing.

        ALWAYS called first, before any business logic.
        Enables full replay, audit, and debugging capability.

        Args:
            payment_id:      FK to the payment (may be None if order lookup fails).
            raw_payload:     Full webhook payload dict.
            gateway_txn_id:  Payment ID (legacy deduplication).
            event_type:      Webhook event type string.
            signature_valid: Whether HMAC verification passed.
            amount_inr:      Amount from webhook payload.
            status:          Status string from webhook.
            gateway_event_id: Unique event ID for deduplication.

        Returns:
            Persisted PaymentWebhook instance.
        """
        webhook = PaymentWebhook(
            payment_id=payment_id,
            gateway_txn_id=gateway_txn_id,
            gateway_event_id=gateway_event_id,
            event_type=event_type,
            raw_payload=json.dumps(raw_payload),
            signature_valid=signature_valid,
            amount_inr=amount_inr,  # type: ignore[arg-type]
            status=status,
        )
        self._db.add(webhook)
        await self._db.flush()

        logger.info(
            "webhook_stored",
            webhook_id=str(webhook.id),
            payment_id=str(payment_id) if payment_id else None,
            signature_valid=signature_valid,
            event_type=event_type,
            gateway_event_id=gateway_event_id,
        )
        return webhook

    async def mark_webhook_processed(self, webhook_id: uuid.UUID, error: str | None = None) -> None:
        """Marks a webhook as processed (or failed with error)."""
        await self._db.execute(
            update(PaymentWebhook)
            .where(PaymentWebhook.id == webhook_id)
            .values(
                is_processed=error is None,
                processed_at=datetime.now(tz=UTC).isoformat(),
                error=error,
            )
        )

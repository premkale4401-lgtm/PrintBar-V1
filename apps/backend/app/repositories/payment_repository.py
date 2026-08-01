"""
PrintBar Backend — Payment Repository

Data access layer for Payment and PaymentWebhook records.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
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
        expires_at = (
            now + timedelta(minutes=settings.PAYMENT_TIMEOUT_MINUTES)
        ).isoformat()

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
        result = await self._db.execute(
            select(Payment).where(Payment.id == payment_id)
        )
        return result.scalar_one_or_none()

    async def get_by_gateway_order_id(self, gateway_order_id: str) -> Payment | None:
        result = await self._db.execute(
            select(Payment).where(Payment.gateway_order_id == gateway_order_id)
        )
        return result.scalar_one_or_none()

    async def get_by_print_job_id(self, print_job_id: uuid.UUID) -> Payment | None:
        result = await self._db.execute(
            select(Payment).where(Payment.print_job_id == print_job_id)
        )
        return result.scalar_one_or_none()

    async def update_gateway_order_id(
        self, payment_id: uuid.UUID, gateway_order_id: str
    ) -> None:
        """Sets the gateway order ID after Easebuzz initiation succeeds."""
        await self._db.execute(
            update(Payment)
            .where(Payment.id == payment_id)
            .values(
                gateway_order_id=gateway_order_id,
                status="PENDING",
            )
        )

    async def mark_success(
        self,
        payment_id: uuid.UUID,
        gateway_txn_id: str,
        payment_mode: str | None,
        vpa: str | None,
        bank_ref: str | None,
    ) -> None:
        """Marks a payment as SUCCESS after verified webhook."""
        await self._db.execute(
            update(Payment)
            .where(Payment.id == payment_id)
            .values(
                status="SUCCESS",
                gateway_txn_id=gateway_txn_id,
                payment_mode=payment_mode,
                vpa=vpa,
                bank_ref=bank_ref,
                paid_at=datetime.now(tz=UTC).isoformat(),
            )
        )
        logger.info("payment_marked_success", payment_id=str(payment_id))

    async def mark_failed(
        self, payment_id: uuid.UUID, reason: str = "GATEWAY_FAILURE"
    ) -> None:
        """Marks a payment as FAILED."""
        await self._db.execute(
            update(Payment)
            .where(Payment.id == payment_id)
            .values(status="FAILED")
        )
        logger.info("payment_marked_failed", payment_id=str(payment_id), reason=reason)

    async def mark_expired(self, payment_id: uuid.UUID) -> None:
        """Marks a payment as EXPIRED."""
        await self._db.execute(
            update(Payment)
            .where(Payment.id == payment_id)
            .values(status="EXPIRED")
        )

    async def store_webhook(
        self,
        payment_id: uuid.UUID | None,
        raw_payload: dict,
        gateway_txn_id: str | None,
        event_type: str,
        signature_valid: bool,
        amount_inr: object | None = None,
        status: str | None = None,
    ) -> PaymentWebhook:
        """
        Stores a raw webhook payload verbatim before any processing.

        This is always called FIRST before any business logic.
        Enables replay and audit.
        """
        webhook = PaymentWebhook(
            payment_id=payment_id,
            gateway_txn_id=gateway_txn_id,
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
        )
        return webhook

    async def mark_webhook_processed(
        self, webhook_id: uuid.UUID, error: str | None = None
    ) -> None:
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

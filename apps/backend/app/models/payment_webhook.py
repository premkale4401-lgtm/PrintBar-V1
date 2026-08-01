"""
PrintBar Backend — PaymentWebhook Model

Immutable record of every webhook event received from Easebuzz.

Every incoming webhook payload is stored verbatim (raw JSON) before
any processing occurs. This enables:
    - Replay: reprocess a webhook if the handler failed.
    - Audit: full history of all payment events.
    - Debugging: inspect exactly what Easebuzz sent.
    - Idempotency: detect and reject duplicate webhooks.

This model is append-only. Records are never updated or deleted.
"""

import uuid
from decimal import Decimal

from sqlalchemy import Boolean, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, UUIDMixin, TimestampMixin


class PaymentWebhook(Base, UUIDMixin, TimestampMixin):
    """
    Raw Easebuzz webhook event record.

    Columns:
        payment_id:          FK to the associated payment.
        gateway_txn_id:      Unique transaction ID from Easebuzz (deduplication key).
        event_type:          Easebuzz event type (e.g., "payment.success").
        raw_payload:         Full raw JSON payload received from Easebuzz.
        signature_valid:     True if HMAC-SHA512 signature verification passed.
        is_processed:        True if the webhook handler completed successfully.
        processed_at:        Timestamp of successful processing.
        error:               Error message if processing failed.
        amount_inr:          Amount from the webhook payload.
        status:              Payment status from the webhook payload.
    """

    __tablename__ = "payment_webhooks"

    payment_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("payments.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    gateway_txn_id: Mapped[str | None] = mapped_column(
        String(256), nullable=True, unique=True, index=True
    )
    event_type: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    raw_payload: Mapped[str] = mapped_column(Text, nullable=False)
    signature_valid: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_processed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    processed_at: Mapped[str | None] = mapped_column(String(50), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    amount_inr: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    status: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # Relationships
    payment: Mapped["Payment | None"] = relationship(  # noqa: F821
        "Payment", back_populates="webhooks"
    )

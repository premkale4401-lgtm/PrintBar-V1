"""
PrintBar Backend — Payment Model

Represents a payment transaction for a print job.

Architecture:
    - A Payment is always created by the backend BEFORE redirecting to Easebuzz.
    - Payment status is updated ONLY by the webhook handler, never by query parameters.
    - All webhook payloads are stored in PaymentWebhook for audit and replay support.
    - Duplicate webhooks are rejected using the idempotency_key.

Security:
    - The payment amount stored here is compared against the webhook amount.
    - Any mismatch triggers a PAY_003 error and the payment is marked FAILED.
    - Signature verification uses HMAC-SHA512 as required by Easebuzz.
"""

import uuid
from decimal import Decimal

from sqlalchemy import Boolean, Enum, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.constants import (
    DEFAULT_CURRENCY,
    PAYMENT_GATEWAY_RAZORPAY,
    PAYMENT_STATUS_CANCELLED,
    PAYMENT_STATUS_CREATED,
    PAYMENT_STATUS_EXPIRED,
    PAYMENT_STATUS_FAILED,
    PAYMENT_STATUS_PENDING,
    PAYMENT_STATUS_PROCESSING,
    PAYMENT_STATUS_REFUNDED,
    PAYMENT_STATUS_SUCCESS,
    PAYMENT_STATUS_VERIFYING,
)
from app.database.base import PrintBarBase


class Payment(PrintBarBase):
    """
    Payment record for a print job.

    Columns:
        print_job_id:        FK to the associated print job.
        gateway:             Payment gateway used (always EASEBUZZ for now).
        gateway_order_id:    Transaction ID assigned by Easebuzz.
        gateway_txn_id:      Bank transaction reference from Easebuzz webhook.
        status:              Current payment status.
        amount_inr:          Amount in INR that must be paid (set at creation).
        currency:            Always INR.
        payment_mode:        UPI, CARD, NET_BANKING, etc. (from webhook).
        vpa:                 UPI VPA if payment was via UPI (from webhook).
        bank_ref:            Bank reference number (from webhook).
        is_refunded:         True if payment has been refunded.
        refunded_at:         Timestamp of refund.
        refund_amount_inr:   Amount refunded.
        refund_txn_id:       Gateway refund transaction ID.
        idempotency_key:     Prevents duplicate payment creation for same job.
        expires_at:          When the payment link expires.
        paid_at:             Timestamp of confirmed payment.

    Relationships:
        print_job:  The job this payment is for.
        webhooks:   All webhook events received for this payment.
    """

    __tablename__ = "payments"

    print_job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("print_jobs.id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,  # One payment per job.
        index=True,
    )
    gateway: Mapped[str] = mapped_column(
        String(64), nullable=False, default=PAYMENT_GATEWAY_RAZORPAY
    )
    gateway_order_id: Mapped[str | None] = mapped_column(
        String(256), nullable=True, unique=True, index=True
    )
    gateway_txn_id: Mapped[str | None] = mapped_column(
        String(256), nullable=True, unique=True
    )
    gateway_signature: Mapped[str | None] = mapped_column(
        String(512), nullable=True  # Stored truncated — never full signature.
    )
    verification_time: Mapped[str | None] = mapped_column(
        String(50), nullable=True  # ISO timestamp of backend verification.
    )
    status: Mapped[str] = mapped_column(
        Enum(
            PAYMENT_STATUS_CREATED,
            PAYMENT_STATUS_PENDING,
            PAYMENT_STATUS_VERIFYING,
            PAYMENT_STATUS_PROCESSING,
            PAYMENT_STATUS_SUCCESS,
            PAYMENT_STATUS_FAILED,
            PAYMENT_STATUS_EXPIRED,
            PAYMENT_STATUS_REFUNDED,
            PAYMENT_STATUS_CANCELLED,
            name="payment_status_enum",
        ),
        nullable=False,
        default=PAYMENT_STATUS_CREATED,
        index=True,
    )
    amount_inr: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default=DEFAULT_CURRENCY)
    payment_mode: Mapped[str | None] = mapped_column(String(64), nullable=True)
    vpa: Mapped[str | None] = mapped_column(String(255), nullable=True)
    bank_ref: Mapped[str | None] = mapped_column(String(256), nullable=True)
    is_refunded: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    refunded_at: Mapped[str | None] = mapped_column(String(50), nullable=True)
    refund_amount_inr: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    refund_txn_id: Mapped[str | None] = mapped_column(String(256), nullable=True)
    idempotency_key: Mapped[str] = mapped_column(
        String(128), nullable=False, unique=True, index=True
    )
    expires_at: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    paid_at: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Relationships
    print_job: Mapped["PrintJob"] = relationship("PrintJob", back_populates="payment")  # noqa: F821
    webhooks: Mapped[list["PaymentWebhook"]] = relationship(  # noqa: F821
        "PaymentWebhook", back_populates="payment", cascade="all, delete-orphan"
    )

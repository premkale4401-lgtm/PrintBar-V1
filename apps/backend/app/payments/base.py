"""
PrintBar Backend — Payment Provider Abstraction

Defines the PaymentProvider protocol that all payment gateway adapters must implement.
Business logic NEVER imports a specific gateway directly — only this protocol.

Supported providers (via registry.py):
    - RazorpayProvider   (current)
    - EasebuzzProvider   (future)
    - CashfreeProvider   (future)
    - PhonePeProvider    (future)

The frontend never knows which provider is active.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class OrderResult:
    """
    Returned by create_order().

    Attributes:
        gateway_order_id: Gateway-assigned order ID (e.g. "order_XXXX" for Razorpay).
        amount_paise:     Amount in smallest currency unit (paise for INR).
        currency:         ISO-4217 currency code (always "INR" for PrintBar).
        receipt:          Internal receipt/job reference we sent.
        status:           Gateway order status (e.g. "created").
        raw:              Full raw response dict from the gateway for audit.
    """

    gateway_order_id: str
    amount_paise: int
    currency: str
    receipt: str
    status: str
    raw: dict


@dataclass(frozen=True)
class WebhookResult:
    """
    Returned by verify_webhook().

    Attributes:
        event_type:       Gateway event type (e.g. "payment.captured").
        gateway_order_id: Associated order ID.
        gateway_txn_id:   Payment/transaction ID from the gateway.
        amount_paise:     Amount paid in paise.
        currency:         Currency code.
        payment_mode:     Payment method used (e.g. "UPI", "CARD").
        vpa:              UPI VPA if payment was via UPI.
        bank_ref:         Bank reference number.
        is_payment_success: True if event indicates a successful payment.
        raw:              Full raw payload dict.
    """

    event_type: str
    gateway_event_id: str | None
    gateway_order_id: str
    gateway_txn_id: str
    amount_paise: int
    currency: str
    payment_mode: str | None
    vpa: str | None
    bank_ref: str | None
    is_payment_success: bool
    raw: dict


@dataclass(frozen=True)
class RefundResult:
    """
    Returned by refund().

    Attributes:
        refund_id:        Gateway refund ID.
        amount_paise:     Refunded amount in paise.
        status:           Refund status (e.g. "processed").
        raw:              Full raw response dict.
    """

    refund_id: str
    amount_paise: int
    status: str
    raw: dict


@dataclass(frozen=True)
class OrderStatus:
    """
    Returned by get_order_status().

    Attributes:
        gateway_order_id: Order ID.
        status:           Gateway order status.
        amount_paid_paise: Total amount paid so far in paise (0 if unpaid).
        payment_count:    Number of payment attempts.
        is_paid:          True if order is fully paid.
    """

    gateway_order_id: str
    status: str
    amount_paid_paise: int
    payment_count: int
    is_paid: bool


@runtime_checkable
class PaymentProvider(Protocol):
    """
    Protocol (interface) that all payment gateway adapters must implement.

    Business logic depends only on this protocol — never on a concrete gateway class.
    To add a new payment gateway, implement this protocol and register it in registry.py.

    All monetary amounts use Decimal INR internally.
    Conversion to/from paise is the adapter's responsibility.
    """

    async def create_order(
        self,
        amount_inr: Decimal,
        receipt_id: str,
        notes: dict | None = None,
    ) -> OrderResult:
        """
        Creates a payment order with the gateway.

        Args:
            amount_inr: Amount to charge in INR (Decimal).
            receipt_id: Our internal receipt reference (job UUID, max 40 chars).
            notes:      Optional metadata to attach to the order.

        Returns:
            OrderResult with gateway_order_id and amount details.

        Raises:
            PaymentAmountMismatchError: If amount is below gateway minimum.
            PaymentGatewayError:        On any gateway API error.
        """
        ...

    def verify_signature(
        self,
        order_id: str,
        payment_id: str,
        received_signature: str,
    ) -> bool:
        """
        Verifies the callback signature from the payment gateway.

        Uses constant-time HMAC comparison to prevent timing attacks.
        Called after the payment modal/redirect completes.

        Args:
            order_id:           Gateway order ID from the callback.
            payment_id:         Gateway payment ID from the callback.
            received_signature: Signature string from the callback payload.

        Returns:
            True if signature is valid, False otherwise.
        """
        ...

    def verify_webhook(
        self,
        raw_body: bytes,
        signature_header: str,
    ) -> WebhookResult:
        """
        Verifies a webhook payload from the gateway.

        MUST verify the HMAC signature of the raw body before parsing.
        Never trust parsed JSON before signature verification.

        Args:
            raw_body:         Raw HTTP request body bytes (not parsed JSON).
            signature_header: Value of the gateway's signature header.

        Returns:
            WebhookResult with parsed event data.

        Raises:
            InvalidPaymentSignatureError: If signature verification fails.
        """
        ...

    async def refund(
        self,
        gateway_payment_id: str,
        amount_inr: Decimal,
        notes: dict | None = None,
    ) -> RefundResult:
        """
        Initiates a refund for a completed payment.

        Args:
            gateway_payment_id: The payment ID to refund.
            amount_inr:         Amount to refund (Decimal INR). Must be <= original.
            notes:              Optional metadata.

        Returns:
            RefundResult with refund_id and status.

        Raises:
            PaymentGatewayError: On any gateway API error.
        """
        ...

    async def get_order_status(
        self,
        gateway_order_id: str,
    ) -> OrderStatus:
        """
        Fetches the current payment status of an order from the gateway.

        Used for QR payment polling — the gateway is the source of truth.

        Args:
            gateway_order_id: The gateway order ID to query.

        Returns:
            OrderStatus with payment details.

        Raises:
            PaymentGatewayError: On any gateway API error.
        """
        ...

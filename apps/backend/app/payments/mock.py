"""
PrintBar Backend — Mock Payment Provider

A fully compliant PaymentProvider implementation for development and CI.

Usage:
    Set PAYMENT_PROVIDER=mock in your .env file.
    No credentials required.
    Complete payments via POST /api/v1/payments/dev/complete.

This provider satisfies every method of the PaymentProvider protocol so it can be
swapped with Razorpay or any real gateway without changing business logic.

Security:
    This provider is registered by registry.py only when PAYMENT_PROVIDER=mock.
    It can never be active in production (enforced by both registry and config validator).
"""

from __future__ import annotations

import secrets
import asyncio
from decimal import Decimal

from app.core.config import get_settings
from app.core.logging import get_logger
from app.payments.base import OrderResult, OrderStatus, RefundResult, WebhookResult

logger = get_logger(__name__)
settings = get_settings()


class MockPaymentProvider:
    """
    Mock implementation of the PaymentProvider protocol.

    All amounts are accepted, all signatures validate, and order status is always paid.
    Used exclusively in PAYMENT_PROVIDER=mock mode to enable end-to-end testing
    without a real payment gateway.

    Never instantiated in staging or production.
    """

    # ─── Order Creation ────────────────────────────────────────────────────────

    async def create_order(
        self,
        amount_inr: Decimal,
        receipt_id: str,
        notes: dict | None = None,
    ) -> OrderResult:
        """
        Creates a fake gateway order.

        Returns a deterministic order ID using the receipt_id so that idempotency
        checks remain consistent (same receipt → same mock order ID).

        Args:
            amount_inr: Amount in INR (Decimal). Must be > 0.
            receipt_id: Internal receipt/job reference (max 40 chars).
            notes:      Optional metadata dict (ignored in mock mode).

        Returns:
            OrderResult with a stable mock gateway_order_id.
        """
        await asyncio.sleep(settings.MOCK_PAYMENT_DELAY_SECONDS)

        # Stable mock order ID: prefix + first 20 chars of receipt_id.
        mock_order_id = f"mock_order_{receipt_id[:20].replace('-', '')}"
        amount_paise = int(amount_inr * 100)

        logger.info(
            "mock_order_created",
            receipt_id=receipt_id,
            mock_order_id=mock_order_id,
            amount_paise=amount_paise,
        )

        return OrderResult(
            gateway_order_id=mock_order_id,
            amount_paise=amount_paise,
            currency="INR",
            receipt=receipt_id,
            status="created",
            raw={
                "id": mock_order_id,
                "entity": "order",
                "amount": amount_paise,
                "amount_paid": 0,
                "amount_due": amount_paise,
                "currency": "INR",
                "receipt": receipt_id,
                "status": "created",
                "notes": notes or {},
                "_mock": True,
            },
        )

    # ─── Signature Verification ────────────────────────────────────────────────

    def verify_signature(
        self,
        order_id: str,
        payment_id: str,
        received_signature: str,
    ) -> bool:
        """
        Mock signature verification — always returns True.

        In mock mode, the dev/complete endpoint bypasses the callback flow entirely,
        so this method is provided for protocol compliance but is never called in
        the primary mock payment workflow.

        Args:
            order_id:           Gateway order ID.
            payment_id:         Gateway payment ID.
            received_signature: Signature from callback (ignored in mock mode).

        Returns:
            Always True.
        """
        logger.debug(
            "mock_signature_verified",
            order_id=order_id,
            payment_id=payment_id,
        )
        return True

    # ─── Webhook Verification ──────────────────────────────────────────────────

    def verify_webhook(
        self,
        raw_body: bytes,
        signature_header: str,
    ) -> WebhookResult:
        """
        Mock webhook verification — raises NotImplementedError.

        In mock mode, payment completion is triggered via POST /payments/dev/complete
        rather than via a real webhook. This method exists for protocol compliance.

        Raises:
            NotImplementedError: Always. Use dev/complete endpoint instead.
        """
        raise NotImplementedError(
            "MockPaymentProvider does not process webhooks. "
            "Use POST /api/v1/payments/dev/complete to simulate payment completion."
        )

    # ─── Refund ────────────────────────────────────────────────────────────────

    async def refund(
        self,
        gateway_payment_id: str,
        amount_inr: Decimal,
        notes: dict | None = None,
    ) -> RefundResult:
        """
        Creates a mock refund record.

        Args:
            gateway_payment_id: The payment ID to refund.
            amount_inr:         Amount to refund (Decimal INR).
            notes:              Optional metadata (ignored in mock mode).

        Returns:
            RefundResult with a generated mock refund ID and status "processed".
        """
        mock_refund_id = f"mock_refund_{secrets.token_hex(8)}"
        amount_paise = int(amount_inr * 100)

        logger.info(
            "mock_refund_processed",
            mock_refund_id=mock_refund_id,
            gateway_payment_id=gateway_payment_id,
            amount_inr=str(amount_inr),
        )

        return RefundResult(
            refund_id=mock_refund_id,
            amount_paise=amount_paise,
            status="processed",
            raw={
                "id": mock_refund_id,
                "payment_id": gateway_payment_id,
                "amount": amount_paise,
                "status": "processed",
                "_mock": True,
            },
        )

    # ─── Order Status Polling ──────────────────────────────────────────────────

    async def get_order_status(
        self,
        gateway_order_id: str,
    ) -> OrderStatus:
        """
        Returns a mock order status.

        Mock orders with IDs starting with "mock_order_" are always considered paid.
        This supports the QR polling flow even in mock mode.

        Args:
            gateway_order_id: The mock order ID to query.

        Returns:
            OrderStatus with is_paid=True for any mock order ID.
        """
        await asyncio.sleep(settings.MOCK_PAYMENT_DELAY_SECONDS)
        
        is_mock = gateway_order_id.startswith("mock_order_")

        logger.debug(
            "mock_order_status_polled",
            gateway_order_id=gateway_order_id,
            is_paid=is_mock,
        )

        return OrderStatus(
            gateway_order_id=gateway_order_id,
            status="paid" if is_mock else "created",
            amount_paid_paise=0,
            payment_count=1 if is_mock else 0,
            is_paid=is_mock,
        )


# Module-level singleton — shared across the application lifetime.
mock_provider = MockPaymentProvider()

"""
PrintBar Backend — Razorpay Payment Gateway Adapter

Implements the PaymentProvider protocol for Razorpay Standard Checkout.

Security requirements:
    - RAZORPAY_KEY_SECRET:      Signs payment callbacks. NEVER logged or returned to frontend.
    - RAZORPAY_WEBHOOK_SECRET:  Signs webhook payloads. Different from KEY_SECRET. NEVER logged.
    - RAZORPAY_KEY_ID:          Public key — safe to return to frontend for modal initialization.
    - All HMAC comparisons use hmac.compare_digest (constant-time) to prevent timing attacks.
    - Webhook verification always operates on RAW bytes — never on parsed JSON.

Razorpay HMAC-SHA256 (Standard Checkout callback):
    signature = HMAC_SHA256(
        key     = RAZORPAY_KEY_SECRET,
        message = f"{razorpay_order_id}|{razorpay_payment_id}"
    )

Razorpay HMAC-SHA256 (Webhook):
    signature = HMAC_SHA256(
        key     = RAZORPAY_WEBHOOK_SECRET,
        message = <raw_request_body_bytes>
    )
"""

from __future__ import annotations

import hashlib
import hmac
import json
from decimal import Decimal

import httpx

from app.core.config import get_settings
from app.core.logging import get_logger
from app.exceptions.base import (
    InvalidPaymentSignatureError,
    PaymentAmountMismatchError,
    PaymentGatewayError,
)
from app.payments.base import OrderResult, OrderStatus, RefundResult, WebhookResult

logger = get_logger(__name__)
settings = get_settings()

# Razorpay enforces a minimum order amount of ₹1.00 (100 paise).
_RAZORPAY_MIN_AMOUNT_INR = Decimal("1.00")
_PAISE_PER_RUPEE = 100

# Razorpay webhook event types we care about.
_EVENT_PAYMENT_CAPTURED = "payment.captured"
_EVENT_PAYMENT_FAILED = "payment.failed"
_EVENT_ORDER_PAID = "order.paid"


class RazorpayProvider:
    """
    Razorpay implementation of the PaymentProvider protocol.

    Responsibilities:
        - Create payment orders via Razorpay Orders API (Basic Auth with KEY_ID + KEY_SECRET).
        - Verify callback HMAC-SHA256 signatures (KEY_SECRET).
        - Verify webhook HMAC-SHA256 signatures (WEBHOOK_SECRET — different secret).
        - Validate payment amounts (paise ↔ INR conversion).
        - Fetch order payment status for QR polling.
        - Initiate refunds.

    The KEY_SECRET and WEBHOOK_SECRET are read once at instantiation.
    They are NEVER stored in logs, responses, or database fields.
    """

    def __init__(self) -> None:
        self._key_id = settings.RAZORPAY_KEY_ID
        self._key_secret = settings.RAZORPAY_KEY_SECRET
        self._webhook_secret = settings.RAZORPAY_WEBHOOK_SECRET
        self._base_url = settings.RAZORPAY_BASE_URL
        self._currency = settings.RAZORPAY_CURRENCY

    # ── Internal helpers ──────────────────────────────────────────────────────

    @property
    def key_id(self) -> str:
        """Public KEY_ID — safe to return to frontend for modal initialization."""
        return self._key_id

    @property
    def _auth(self) -> tuple[str, str]:
        """Basic Auth tuple. Secret is never logged."""
        return (self._key_id, self._key_secret)

    @staticmethod
    def inr_to_paise(amount_inr: Decimal) -> int:
        """Converts INR Decimal to paise integer (Razorpay's required unit)."""
        return int((amount_inr * _PAISE_PER_RUPEE).to_integral_value())

    @staticmethod
    def paise_to_inr(amount_paise: int) -> Decimal:
        """Converts paise integer back to INR Decimal."""
        return Decimal(amount_paise) / _PAISE_PER_RUPEE

    # ── Order Creation ────────────────────────────────────────────────────────

    async def create_order(
        self,
        amount_inr: Decimal,
        receipt_id: str,
        notes: dict | None = None,
    ) -> OrderResult:
        """
        Creates a Razorpay order via the Orders API.

        Args:
            amount_inr:  Payment amount in INR (Decimal).
            receipt_id:  Internal receipt ID (max 40 chars — our job UUID).
            notes:       Optional key-value metadata.

        Returns:
            OrderResult with gateway_order_id and amount details.

        Raises:
            PaymentAmountMismatchError: Amount below ₹1.00 minimum.
            PaymentGatewayError:        Any Razorpay API error.
        """
        if amount_inr < _RAZORPAY_MIN_AMOUNT_INR:
            logger.error(
                "razorpay_amount_below_minimum",
                amount_inr=str(amount_inr),
                minimum_inr=str(_RAZORPAY_MIN_AMOUNT_INR),
            )
            raise PaymentAmountMismatchError()

        amount_paise = self.inr_to_paise(amount_inr)

        payload = {
            "amount": amount_paise,
            "currency": self._currency,
            "receipt": receipt_id[:40],
            "notes": notes or {},
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self._base_url}/orders",
                    json=payload,
                    auth=self._auth,
                    headers={"Content-Type": "application/json"},
                )

                if response.status_code != 200:
                    logger.error(
                        "razorpay_create_order_http_error",
                        receipt_id=receipt_id,
                        status_code=response.status_code,
                        response_body=response.text[:200],
                    )
                    raise PaymentGatewayError()

                data = response.json()

                if not data.get("id") or not data.get("amount"):
                    logger.error(
                        "razorpay_create_order_invalid_response",
                        receipt_id=receipt_id,
                    )
                    raise PaymentGatewayError()

                logger.info(
                    "razorpay_order_created",
                    receipt_id=receipt_id,
                    razorpay_order_id=data["id"],
                    amount_paise=data["amount"],
                )

                return OrderResult(
                    gateway_order_id=data["id"],
                    amount_paise=data["amount"],
                    currency=data.get("currency", self._currency),
                    receipt=data.get("receipt", receipt_id),
                    status=data.get("status", "created"),
                    raw=data,
                )

        except httpx.TimeoutException:
            logger.error("razorpay_create_order_timeout", receipt_id=receipt_id)
            raise PaymentGatewayError()
        except httpx.RequestError as exc:
            logger.error("razorpay_create_order_request_error", error=str(exc))
            raise PaymentGatewayError()
        except (PaymentGatewayError, PaymentAmountMismatchError):
            raise
        except Exception as exc:
            logger.exception("razorpay_create_order_unexpected", error=str(exc))
            raise PaymentGatewayError()

    # ── Callback Signature Verification ───────────────────────────────────────

    def _compute_callback_signature(self, order_id: str, payment_id: str) -> str:
        """
        Computes HMAC-SHA256 signature for Standard Checkout callback.
        Formula: HMAC_SHA256(KEY_SECRET, f"{order_id}|{payment_id}")
        """
        message = f"{order_id}|{payment_id}"
        return hmac.new(
            key=self._key_secret.encode("utf-8"),
            msg=message.encode("utf-8"),
            digestmod=hashlib.sha256,
        ).hexdigest()

    def verify_signature(
        self,
        order_id: str,
        payment_id: str,
        received_signature: str,
    ) -> bool:
        """
        Verifies Razorpay payment callback signature (constant-time comparison).

        Args:
            order_id:           Razorpay order ID from callback.
            payment_id:         Razorpay payment ID from callback.
            received_signature: Signature from callback payload.

        Returns:
            True if valid, False otherwise.
        """
        expected = self._compute_callback_signature(order_id, payment_id)
        result = hmac.compare_digest(expected, received_signature.lower())

        if not result:
            logger.warning(
                "razorpay_signature_mismatch",
                order_id=order_id,
                payment_id=payment_id,
                # NEVER log received_signature — it may be an attacker probe.
            )

        return result

    # ── Webhook Verification ──────────────────────────────────────────────────

    def verify_webhook(
        self,
        raw_body: bytes,
        signature_header: str,
    ) -> WebhookResult:
        """
        Verifies a Razorpay webhook payload.

        CRITICAL: Operates on raw bytes — JSON is only parsed AFTER signature passes.
        Formula: HMAC_SHA256(WEBHOOK_SECRET, raw_body_bytes)

        The webhook secret is different from the payment callback KEY_SECRET.
        Configure it in the Razorpay dashboard under Webhooks.

        Args:
            raw_body:         Raw HTTP request body bytes.
            signature_header: Value of 'X-Razorpay-Signature' header.

        Returns:
            WebhookResult with parsed event data.

        Raises:
            InvalidPaymentSignatureError: Signature is invalid.
        """
        # Step 1: Verify signature BEFORE parsing JSON.
        expected = hmac.new(
            key=self._webhook_secret.encode("utf-8"),
            msg=raw_body,
            digestmod=hashlib.sha256,
        ).hexdigest()

        if not hmac.compare_digest(expected, signature_header.lower()):
            logger.warning(
                "razorpay_webhook_signature_invalid",
                body_length=len(raw_body),
                # Never log signature_header — may be an attacker probe.
            )
            raise InvalidPaymentSignatureError()

        # Step 2: Parse JSON only after signature is verified.
        try:
            payload = json.loads(raw_body.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            logger.error("razorpay_webhook_json_parse_error", error=str(exc))
            raise InvalidPaymentSignatureError()

        # Step 3: Extract event type and payment entity.
        event_type = payload.get("event", "")
        entity = payload.get("payload", {}).get("payment", {}).get("entity", {})
        order_entity = payload.get("payload", {}).get("order", {}).get("entity", {})

        # Use payment entity first; fall back to order entity for order.paid events.
        gateway_event_id = payload.get("id")
        gateway_order_id = entity.get("order_id") or order_entity.get("id", "")
        gateway_txn_id = entity.get("id", "")
        amount_paise = entity.get("amount") or order_entity.get("amount_paid", 0)
        currency = entity.get("currency", self._currency)
        payment_mode = entity.get("method")
        vpa = entity.get("vpa")
        bank_ref = entity.get("bank") or entity.get("acquirer_data", {}).get("bank_transaction_id")

        is_payment_success = event_type in (_EVENT_PAYMENT_CAPTURED, _EVENT_ORDER_PAID)

        logger.info(
            "razorpay_webhook_verified",
            event_type=event_type,
            gateway_event_id=gateway_event_id,
            gateway_order_id=gateway_order_id,
            gateway_txn_id=gateway_txn_id,
            is_payment_success=is_payment_success,
        )

        return WebhookResult(
            event_type=event_type,
            gateway_event_id=gateway_event_id,
            gateway_order_id=gateway_order_id,
            gateway_txn_id=gateway_txn_id,
            amount_paise=int(amount_paise or 0),
            currency=currency,
            payment_mode=payment_mode,
            vpa=vpa,
            bank_ref=bank_ref,
            is_payment_success=is_payment_success,
            raw=payload,
        )

    # ── Amount Verification ───────────────────────────────────────────────────

    def verify_amount(
        self,
        razorpay_amount_paise: int,
        expected_amount_inr: Decimal,
    ) -> None:
        """
        Verifies that the Razorpay payment amount matches the stored order amount.

        Args:
            razorpay_amount_paise: Amount in paise from Razorpay.
            expected_amount_inr:   Amount in INR from the Payment DB record.

        Raises:
            PaymentAmountMismatchError: If amounts do not match exactly.
        """
        received_inr = self.paise_to_inr(razorpay_amount_paise).quantize(Decimal("0.01"))
        expected_inr = expected_amount_inr.quantize(Decimal("0.01"))

        if received_inr != expected_inr:
            logger.error(
                "razorpay_amount_mismatch",
                received_paise=razorpay_amount_paise,
                received_inr=str(received_inr),
                expected_inr=str(expected_inr),
            )
            raise PaymentAmountMismatchError()

    # ── Order Status (for QR polling) ─────────────────────────────────────────

    async def get_order_status(self, gateway_order_id: str) -> OrderStatus:
        """
        Fetches the current payment status of a Razorpay order.

        Used for QR payment polling — polls GET /v1/orders/{id}/payments
        to check if the customer has completed the UPI payment.

        Args:
            gateway_order_id: Razorpay order ID (e.g. "order_XXXX").

        Returns:
            OrderStatus with is_paid flag.

        Raises:
            PaymentGatewayError: On any API error.
        """
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(
                    f"{self._base_url}/orders/{gateway_order_id}/payments",
                    auth=self._auth,
                )

                if response.status_code == 404:
                    logger.warning(
                        "razorpay_order_not_found",
                        gateway_order_id=gateway_order_id,
                    )
                    return OrderStatus(
                        gateway_order_id=gateway_order_id,
                        status="not_found",
                        amount_paid_paise=0,
                        payment_count=0,
                        is_paid=False,
                    )

                if response.status_code != 200:
                    logger.error(
                        "razorpay_get_order_status_http_error",
                        gateway_order_id=gateway_order_id,
                        status_code=response.status_code,
                    )
                    raise PaymentGatewayError()

                data = response.json()
                items = data.get("items", [])
                payment_count = data.get("count", len(items))

                # Find the captured payment if any.
                captured = next((p for p in items if p.get("status") == "captured"), None)
                is_paid = captured is not None
                amount_paid_paise = captured.get("amount", 0) if captured else 0

                logger.info(
                    "razorpay_order_status_fetched",
                    gateway_order_id=gateway_order_id,
                    is_paid=is_paid,
                    payment_count=payment_count,
                )

                return OrderStatus(
                    gateway_order_id=gateway_order_id,
                    status="paid" if is_paid else "created",
                    amount_paid_paise=amount_paid_paise,
                    payment_count=payment_count,
                    is_paid=is_paid,
                )

        except httpx.TimeoutException:
            logger.error(
                "razorpay_get_order_status_timeout",
                gateway_order_id=gateway_order_id,
            )
            raise PaymentGatewayError()
        except httpx.RequestError as exc:
            logger.error("razorpay_get_order_status_request_error", error=str(exc))
            raise PaymentGatewayError()
        except PaymentGatewayError:
            raise
        except Exception as exc:
            logger.exception("razorpay_get_order_status_unexpected", error=str(exc))
            raise PaymentGatewayError()

    # ── Refunds ───────────────────────────────────────────────────────────────

    async def refund(
        self,
        gateway_payment_id: str,
        amount_inr: Decimal,
        notes: dict | None = None,
    ) -> RefundResult:
        """
        Initiates a refund via Razorpay Refunds API.

        Args:
            gateway_payment_id: Razorpay payment ID (e.g. "pay_XXXX").
            amount_inr:         Amount to refund in INR (Decimal).
            notes:              Optional metadata.

        Returns:
            RefundResult with refund_id and status.

        Raises:
            PaymentGatewayError: On any API error.
        """
        amount_paise = self.inr_to_paise(amount_inr)

        payload: dict = {
            "amount": amount_paise,
            "speed": "normal",
            "notes": notes or {},
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self._base_url}/payments/{gateway_payment_id}/refund",
                    json=payload,
                    auth=self._auth,
                    headers={"Content-Type": "application/json"},
                )

                if response.status_code not in (200, 201):
                    logger.error(
                        "razorpay_refund_http_error",
                        gateway_payment_id=gateway_payment_id,
                        status_code=response.status_code,
                        response_body=response.text[:200],
                    )
                    raise PaymentGatewayError()

                data = response.json()

                logger.info(
                    "razorpay_refund_initiated",
                    gateway_payment_id=gateway_payment_id,
                    refund_id=data.get("id"),
                    amount_paise=amount_paise,
                )

                return RefundResult(
                    refund_id=data.get("id", ""),
                    amount_paise=data.get("amount", amount_paise),
                    status=data.get("status", "created"),
                    raw=data,
                )

        except httpx.TimeoutException:
            logger.error(
                "razorpay_refund_timeout",
                gateway_payment_id=gateway_payment_id,
            )
            raise PaymentGatewayError()
        except httpx.RequestError as exc:
            logger.error("razorpay_refund_request_error", error=str(exc))
            raise PaymentGatewayError()
        except PaymentGatewayError:
            raise
        except Exception as exc:
            logger.exception("razorpay_refund_unexpected", error=str(exc))
            raise PaymentGatewayError()


# ─── Module-level singleton ───────────────────────────────────────────────────
# Instantiated once per process. Use via registry.get_active_provider().
# Do NOT import this directly in business logic — use the registry.
razorpay_provider = RazorpayProvider()

# Backward-compat alias used by existing payment_service.py.
razorpay_gateway = razorpay_provider

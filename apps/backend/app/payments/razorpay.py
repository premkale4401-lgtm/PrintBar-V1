"""
PrintBar Backend — Razorpay Payment Gateway Integration

Handles all Razorpay API interactions:
    - Create payment order (POST /v1/orders via Basic Auth)
    - Verify webhook/callback signature (HMAC-SHA256)
    - Verify payment amount matches stored order (paise vs INR)

Security requirements:
    - RAZORPAY_KEY_SECRET is NEVER logged or returned to the frontend.
    - RAZORPAY_KEY_ID (public key) is returned to the frontend via the
      create-order endpoint so the browser can open the Razorpay modal.
    - Signature verification uses hmac.compare_digest for constant-time
      comparison, preventing timing-based side-channel attacks.
    - Amount verification converts Razorpay's paise to INR and compares
      against the stored Decimal value — never trusts frontend amounts.

Razorpay HMAC-SHA256 signature (Standard Checkout callback):
    signature = HMAC_SHA256(
        key    = RAZORPAY_KEY_SECRET,
        message = f"{razorpay_order_id}|{razorpay_payment_id}"
    )
"""

from __future__ import annotations

import hashlib
import hmac
from decimal import Decimal, InvalidOperation

import httpx

from app.core.config import get_settings
from app.core.logging import get_logger
from app.exceptions.base import (
    InvalidPaymentSignatureError,
    PaymentAmountMismatchError,
    PaymentGatewayError,
)

logger = get_logger(__name__)
settings = get_settings()

# Razorpay enforces a minimum order amount of ₹1.00 (100 paise).
_RAZORPAY_MIN_AMOUNT_INR = Decimal("1.00")
_PAISE_PER_RUPEE = 100


class RazorpayGateway:
    """
    Razorpay payment gateway integration.

    Responsibilities:
        - Create orders via the Razorpay Orders API (Basic Auth).
        - Compute and verify HMAC-SHA256 signatures.
        - Validate payment amounts (paise → INR conversion).

    The KEY_SECRET is read once at instantiation from settings and
    is never stored in any log, response body, or database field.
    """

    def __init__(self) -> None:
        self._key_id = settings.RAZORPAY_KEY_ID
        self._key_secret = settings.RAZORPAY_KEY_SECRET
        self._base_url = settings.RAZORPAY_BASE_URL
        self._currency = settings.RAZORPAY_CURRENCY

    # ── Internal helpers ──────────────────────────────────────────────────────

    @property
    def _auth(self) -> tuple[str, str]:
        """Basic Auth tuple for Razorpay API calls. Secret is never logged."""
        return (self._key_id, self._key_secret)

    @staticmethod
    def inr_to_paise(amount_inr: Decimal) -> int:
        """
        Converts an INR Decimal amount to paise (integer).

        Razorpay requires amounts in the smallest currency unit (paise).

        Args:
            amount_inr: Amount in INR as a Decimal.

        Returns:
            Integer paise value.

        Example:
            ₹7.08 → 708 paise
        """
        return int((amount_inr * _PAISE_PER_RUPEE).to_integral_value())

    @staticmethod
    def paise_to_inr(amount_paise: int) -> Decimal:
        """Converts paise integer back to INR Decimal."""
        return Decimal(amount_paise) / _PAISE_PER_RUPEE

    # ── Signature ─────────────────────────────────────────────────────────────

    def compute_signature(self, order_id: str, payment_id: str) -> str:
        """
        Computes the expected HMAC-SHA256 signature for a Razorpay payment.

        Formula:
            HMAC_SHA256(secret, f"{order_id}|{payment_id}")

        Args:
            order_id:   Razorpay order ID (e.g. "order_XXXX").
            payment_id: Razorpay payment ID (e.g. "pay_XXXX").

        Returns:
            Lowercase hex HMAC-SHA256 string.
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
        Verifies the Razorpay payment signature using constant-time comparison.

        Args:
            order_id:           Razorpay order ID from the callback.
            payment_id:         Razorpay payment ID from the callback.
            received_signature: Signature string from Razorpay callback payload.

        Returns:
            True if signature is valid. False otherwise.
        """
        expected = self.compute_signature(order_id, payment_id)

        # hmac.compare_digest prevents timing attacks.
        result = hmac.compare_digest(expected, received_signature.lower())

        if not result:
            logger.warning(
                "razorpay_signature_mismatch",
                order_id=order_id,
                payment_id=payment_id,
                # Never log the received_signature — it may be an attacker probe.
            )

        return result

    # ── Amount Verification ───────────────────────────────────────────────────

    def verify_amount(
        self,
        razorpay_amount_paise: int,
        expected_amount_inr: Decimal,
    ) -> None:
        """
        Verifies that the Razorpay payment amount matches the stored order amount.

        Razorpay returns amounts in paise. This method converts and compares
        at 2-decimal INR precision.

        Args:
            razorpay_amount_paise: Amount in paise from Razorpay (integer).
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

    # ── Order Creation ────────────────────────────────────────────────────────

    async def create_order(
        self,
        amount_inr: Decimal,
        receipt_id: str,
        notes: dict | None = None,
    ) -> dict:
        """
        Creates a Razorpay order via the Razorpay Orders API.

        Validates minimum amount before making the API call.

        Args:
            amount_inr:  Payment amount in INR (Decimal).
            receipt_id:  Unique receipt identifier (max 40 chars, our job UUID).
            notes:       Optional key-value metadata attached to the order.

        Returns:
            Dict with Razorpay order data:
                - id:         Razorpay order ID (e.g. "order_XXXX")
                - amount:     Amount in paise (integer)
                - currency:   "INR"
                - receipt:    The receipt_id we sent
                - status:     "created"

        Raises:
            PaymentAmountMismatchError: If amount is below ₹1.00 minimum.
            PaymentGatewayError:        On any Razorpay API error.
        """
        # Enforce minimum amount.
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
            "receipt": receipt_id[:40],  # Razorpay max: 40 chars
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
                        # Truncate body to avoid leaking sensitive data in logs.
                        response_body=response.text[:200],
                    )
                    raise PaymentGatewayError()

                data = response.json()

                # Validate required fields are present in response.
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
                return data

        except httpx.TimeoutException:
            logger.error("razorpay_create_order_timeout", receipt_id=receipt_id)
            raise PaymentGatewayError()
        except httpx.RequestError as exc:
            logger.error("razorpay_create_order_request_error", error=str(exc))
            raise PaymentGatewayError()
        except PaymentGatewayError:
            raise
        except PaymentAmountMismatchError:
            raise
        except Exception as exc:
            logger.exception("razorpay_create_order_unexpected", error=str(exc))
            raise PaymentGatewayError()


# Module-level singleton — instantiated once per process.
razorpay_gateway = RazorpayGateway()

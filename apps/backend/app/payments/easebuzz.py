"""
PrintBar Backend — Easebuzz Payment Gateway Integration

Handles all Easebuzz API interactions:
    - Create payment order (initiate transaction)
    - Verify webhook signature (HMAC-SHA512)
    - Verify payment amount matches order

Security requirements (doc 09):
    - All webhook payloads are stored verbatim BEFORE processing.
    - Payment status is updated ONLY after successful signature verification.
    - Amount mismatch triggers immediate failure — never accept partial payments.
    - All Easebuzz requests use HTTPS. Never HTTP.
    - The EASEBUZZ_SALT is never logged.

Easebuzz HMAC-SHA512 signature:
    hash = SHA512(key|txnid|amount|productinfo|firstname|email|
                  udf1|udf2|udf3|udf4|udf5||||||salt)
    
    Webhook verification reversal:
    reverse_hash = SHA512(salt|status||udf5|udf4|udf3|udf2|udf1|
                          email|firstname|productinfo|amount|txnid|key)
"""

from __future__ import annotations

import hashlib
import hmac
from decimal import Decimal

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


class EasebuzzGateway:
    """
    Easebuzz payment gateway integration.

    Responsibilities:
        - Build the payment initiation payload.
        - Compute and verify HMAC-SHA512 signatures.
        - Validate webhook amount against the stored order.
    """

    def __init__(self) -> None:
        self._key = settings.EASEBUZZ_KEY
        self._salt = settings.EASEBUZZ_SALT
        self._base_url = settings.EASEBUZZ_BASE_URL
        self._env = settings.EASEBUZZ_ENV

    @property
    def _initiate_url(self) -> str:
        """The Easebuzz payment initiation URL."""
        return f"{self._base_url}/payment/initiateLink"

    def compute_initiation_hash(
        self,
        txnid: str,
        amount: str,
        productinfo: str,
        firstname: str,
        email: str,
        udf1: str = "",
        udf2: str = "",
        udf3: str = "",
        udf4: str = "",
        udf5: str = "",
    ) -> str:
        """
        Computes the HMAC-SHA512 hash for payment initiation.

        Formula:
            key|txnid|amount|productinfo|firstname|email|udf1|udf2|udf3|udf4|udf5||||||salt

        Args:
            txnid:       Unique transaction ID (our print job ID).
            amount:      Amount string formatted to 2 decimal places.
            productinfo: Product description.
            firstname:   Customer first name.
            email:       Customer email (use a placeholder for guest users).
            udf1-5:      User-defined fields.

        Returns:
            Lowercase hex SHA-512 hash string.
        """
        hash_string = (
            f"{self._key}|{txnid}|{amount}|{productinfo}|{firstname}|{email}|"
            f"{udf1}|{udf2}|{udf3}|{udf4}|{udf5}||||||{self._salt}"
        )
        return hashlib.sha512(hash_string.encode("utf-8")).hexdigest()

    def verify_webhook_signature(self, payload: dict) -> bool:
        """
        Verifies the Easebuzz webhook signature.

        Formula (reverse hash):
            salt|status||udf5|udf4|udf3|udf2|udf1|email|firstname|productinfo|amount|txnid|key

        Args:
            payload: Parsed form data from the Easebuzz webhook POST.

        Returns:
            True if signature matches. False otherwise.
        """
        received_hash = payload.get("hash", "")

        reverse_hash_string = (
            f"{self._salt}|{payload.get('status', '')}||"
            f"{payload.get('udf5', '')}|{payload.get('udf4', '')}|"
            f"{payload.get('udf3', '')}|{payload.get('udf2', '')}|"
            f"{payload.get('udf1', '')}|{payload.get('email', '')}|"
            f"{payload.get('firstname', '')}|{payload.get('productinfo', '')}|"
            f"{payload.get('amount', '')}|{payload.get('txnid', '')}|{self._key}"
        )

        computed_hash = hashlib.sha512(
            reverse_hash_string.encode("utf-8")
        ).hexdigest()

        # Use constant-time comparison to prevent timing attacks.
        result = hmac.compare_digest(computed_hash, received_hash.lower())

        if not result:
            logger.warning(
                "easebuzz_signature_mismatch",
                txnid=payload.get("txnid"),
                status=payload.get("status"),
            )

        return result

    def verify_payment_amount(
        self,
        webhook_amount: str,
        expected_amount: Decimal,
    ) -> None:
        """
        Verifies that the webhook payment amount matches the stored order amount.

        Args:
            webhook_amount: Amount string from the Easebuzz webhook payload.
            expected_amount: Amount from the Payment database record.

        Raises:
            PaymentAmountMismatchError: If amounts do not match.
        """
        try:
            received = Decimal(webhook_amount).quantize(Decimal("0.01"))
        except Exception:
            raise PaymentAmountMismatchError()

        expected = expected_amount.quantize(Decimal("0.01"))

        if received != expected:
            logger.error(
                "payment_amount_mismatch",
                received=str(received),
                expected=str(expected),
            )
            raise PaymentAmountMismatchError()

    def build_payment_payload(
        self,
        txnid: str,
        amount: Decimal,
        productinfo: str,
        firstname: str,
        email: str,
        phone: str,
        surl: str,
        furl: str,
        udf1: str = "",
        udf2: str = "",
        udf3: str = "",
        udf4: str = "",
        udf5: str = "",
    ) -> dict:
        """
        Builds the complete payload for Easebuzz payment initiation.

        Args:
            txnid:       Unique transaction ID.
            amount:      Payment amount in INR.
            productinfo: Product description shown on payment page.
            firstname:   Customer first name.
            email:       Customer email.
            phone:       Customer phone number.
            surl:        Success redirect URL (backend webhook endpoint).
            furl:        Failure redirect URL (backend webhook endpoint).
            udf1-5:      User-defined fields for custom data.

        Returns:
            Dict payload ready to POST to Easebuzz.
        """
        amount_str = f"{amount:.2f}"
        hash_value = self.compute_initiation_hash(
            txnid=txnid,
            amount=amount_str,
            productinfo=productinfo,
            firstname=firstname,
            email=email,
            udf1=udf1,
            udf2=udf2,
            udf3=udf3,
            udf4=udf4,
            udf5=udf5,
        )

        return {
            "key": self._key,
            "txnid": txnid,
            "amount": amount_str,
            "productinfo": productinfo,
            "firstname": firstname,
            "email": email,
            "phone": phone,
            "surl": surl,
            "furl": furl,
            "hash": hash_value,
            "udf1": udf1,
            "udf2": udf2,
            "udf3": udf3,
            "udf4": udf4,
            "udf5": udf5,
            "env": self._env,
        }

    async def initiate_payment(
        self,
        txnid: str,
        amount: Decimal,
        productinfo: str,
        firstname: str,
        email: str,
        phone: str,
        surl: str,
        furl: str,
        udf1: str = "",
    ) -> str:
        """
        Initiates a payment via the Easebuzz API and returns the payment URL.

        Args:
            (see build_payment_payload)

        Returns:
            Payment URL to redirect the user to.

        Raises:
            PaymentGatewayError: On any Easebuzz API error.
        """
        payload = self.build_payment_payload(
            txnid=txnid,
            amount=amount,
            productinfo=productinfo,
            firstname=firstname,
            email=email,
            phone=phone,
            surl=surl,
            furl=furl,
            udf1=udf1,
        )

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    self._initiate_url,
                    data=payload,
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                )

                if response.status_code != 200:
                    logger.error(
                        "easebuzz_initiate_http_error",
                        txnid=txnid,
                        status=response.status_code,
                    )
                    raise PaymentGatewayError()

                data = response.json()

                if data.get("status") != 1:
                    logger.error(
                        "easebuzz_initiate_api_error",
                        txnid=txnid,
                        response=str(data)[:200],
                    )
                    raise PaymentGatewayError()

                payment_url = data.get("data")
                if not payment_url:
                    raise PaymentGatewayError()

                logger.info("easebuzz_payment_initiated", txnid=txnid)
                return payment_url

        except httpx.TimeoutException:
            logger.error("easebuzz_initiate_timeout", txnid=txnid)
            raise PaymentGatewayError()
        except httpx.RequestError as exc:
            logger.error("easebuzz_initiate_error", error=str(exc))
            raise PaymentGatewayError()
        except PaymentGatewayError:
            raise
        except Exception as exc:
            logger.exception("easebuzz_initiate_unexpected", error=str(exc))
            raise PaymentGatewayError()


# Module-level singleton.
easebuzz_gateway = EasebuzzGateway()

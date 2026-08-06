"""
PrintBar Backend — Razorpay Payment Gateway Tests

Tests for Razorpay HMAC-SHA256 signature generation, constant-time verification,
webhook signature verification, and paise/INR amount validation.
These are pure unit tests — no DB or network required.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from decimal import Decimal

import pytest

from app.exceptions.base import InvalidPaymentSignatureError, PaymentAmountMismatchError
from app.payments.razorpay import RazorpayProvider


def _make_provider(
    key_id: str = "rzp_test_KEY123",
    key_secret: str = "SECRET456",
    webhook_secret: str = "WEBHOOK_SECRET_789",
) -> RazorpayProvider:
    """Creates a RazorpayProvider with test credentials."""
    provider = RazorpayProvider.__new__(RazorpayProvider)
    provider._key_id = key_id
    provider._key_secret = key_secret
    provider._webhook_secret = webhook_secret
    provider._base_url = "https://api.razorpay.com/v1"
    provider._currency = "INR"
    return provider


class TestRazorpaySignature:
    """Tests for Razorpay HMAC-SHA256 signature generation and verification."""

    def test_signature_deterministic(self) -> None:
        """Same inputs always produce the same HMAC-SHA256 hash."""
        provider = _make_provider()
        s1 = provider._compute_callback_signature("order_123", "pay_456")
        s2 = provider._compute_callback_signature("order_123", "pay_456")
        assert s1 == s2
        assert len(s1) == 64  # SHA-256 hex = 64 chars

    def test_signature_changes_with_order_id(self) -> None:
        provider = _make_provider()
        s1 = provider._compute_callback_signature("order_123", "pay_456")
        s2 = provider._compute_callback_signature("order_999", "pay_456")
        assert s1 != s2

    def test_signature_changes_with_secret(self) -> None:
        p1 = _make_provider(key_secret="SECRET_A")
        p2 = _make_provider(key_secret="SECRET_B")
        s1 = p1._compute_callback_signature("order_123", "pay_456")
        s2 = p2._compute_callback_signature("order_123", "pay_456")
        assert s1 != s2

    def test_verify_signature_pass(self) -> None:
        """Correctly computed signature passes verification."""
        provider = _make_provider(key_secret="MY_SECRET_KEY")
        order_id = "order_abc123"
        payment_id = "pay_xyz789"

        # Compute correct signature manually
        msg = f"{order_id}|{payment_id}"
        expected_sig = hmac.new(b"MY_SECRET_KEY", msg.encode(), hashlib.sha256).hexdigest()

        assert provider.verify_signature(order_id, payment_id, expected_sig) is True

    def test_verify_signature_fail_on_tampered(self) -> None:
        """Tampered signature fails verification."""
        provider = _make_provider()
        tampered_sig = "a" * 64
        assert provider.verify_signature("order_123", "pay_456", tampered_sig) is False


class TestRazorpayWebhookVerification:
    """Tests for Razorpay Webhook signature verification."""

    def test_webhook_signature_pass(self) -> None:
        provider = _make_provider(webhook_secret="MY_WEBHOOK_SECRET")
        payload = {
            "event": "payment.captured",
            "payload": {
                "payment": {
                    "entity": {
                        "id": "pay_123",
                        "order_id": "order_123",
                        "amount": 200,
                        "currency": "INR",
                        "method": "upi",
                        "vpa": "user@upi",
                    }
                }
            },
        }
        raw_body = json.dumps(payload).encode("utf-8")
        expected_sig = hmac.new(b"MY_WEBHOOK_SECRET", raw_body, hashlib.sha256).hexdigest()

        result = provider.verify_webhook(raw_body, expected_sig)
        assert result.is_payment_success is True
        assert result.gateway_order_id == "order_123"
        assert result.gateway_txn_id == "pay_123"
        assert result.amount_paise == 200
        assert result.payment_mode == "upi"
        assert result.vpa == "user@upi"

    def test_webhook_signature_fail(self) -> None:
        provider = _make_provider(webhook_secret="MY_WEBHOOK_SECRET")
        raw_body = b'{"event":"payment.captured"}'
        tampered_sig = "invalid_signature"

        with pytest.raises(InvalidPaymentSignatureError):
            provider.verify_webhook(raw_body, tampered_sig)


class TestRazorpayAmountValidation:
    """Tests for paise / INR conversion and amount verification."""

    def test_inr_to_paise(self) -> None:
        assert RazorpayProvider.inr_to_paise(Decimal("7.08")) == 708
        assert RazorpayProvider.inr_to_paise(Decimal("100.00")) == 10000
        assert RazorpayProvider.inr_to_paise(Decimal("1.50")) == 150

    def test_paise_to_inr(self) -> None:
        assert RazorpayProvider.paise_to_inr(708) == Decimal("7.08")
        assert RazorpayProvider.paise_to_inr(10000) == Decimal("100.00")

    def test_verify_amount_pass_on_match(self) -> None:
        provider = _make_provider()
        provider.verify_amount(708, Decimal("7.08"))

    def test_verify_amount_fail_on_mismatch(self) -> None:
        provider = _make_provider()
        with pytest.raises(PaymentAmountMismatchError):
            provider.verify_amount(708, Decimal("10.00"))

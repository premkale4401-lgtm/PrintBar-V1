"""
PrintBar Backend — Razorpay Payment Gateway Tests

Tests for Razorpay HMAC-SHA256 signature generation, constant-time verification,
and paise/INR amount validation.
These are pure unit tests — no DB or network required.
"""
from __future__ import annotations

import hashlib
import hmac
from decimal import Decimal
from unittest.mock import patch

import pytest

from app.payments.razorpay import RazorpayGateway


def _make_gateway(key_id: str = "rzp_test_KEY123", key_secret: str = "SECRET456") -> RazorpayGateway:
    """Creates a RazorpayGateway with test credentials."""
    gw = RazorpayGateway.__new__(RazorpayGateway)
    gw._key_id = key_id
    gw._key_secret = key_secret
    gw._base_url = "https://api.razorpay.com/v1"
    gw._currency = "INR"
    return gw


class TestRazorpaySignature:
    """Tests for Razorpay HMAC-SHA256 signature generation and verification."""

    def test_signature_deterministic(self) -> None:
        """Same inputs always produce the same HMAC-SHA256 hash."""
        gw = _make_gateway()
        s1 = gw.compute_signature("order_123", "pay_456")
        s2 = gw.compute_signature("order_123", "pay_456")
        assert s1 == s2
        assert len(s1) == 64  # SHA-256 hex = 64 chars

    def test_signature_changes_with_order_id(self) -> None:
        gw = _make_gateway()
        s1 = gw.compute_signature("order_123", "pay_456")
        s2 = gw.compute_signature("order_999", "pay_456")
        assert s1 != s2

    def test_signature_changes_with_secret(self) -> None:
        gw1 = _make_gateway(key_secret="SECRET_A")
        gw2 = _make_gateway(key_secret="SECRET_B")
        s1 = gw1.compute_signature("order_123", "pay_456")
        s2 = gw2.compute_signature("order_123", "pay_456")
        assert s1 != s2

    def test_verify_signature_pass(self) -> None:
        """Correctly computed signature passes verification."""
        gw = _make_gateway(key_secret="MY_SECRET_KEY")
        order_id = "order_abc123"
        payment_id = "pay_xyz789"

        # Compute correct signature manually
        msg = f"{order_id}|{payment_id}"
        expected_sig = hmac.new(b"MY_SECRET_KEY", msg.encode(), hashlib.sha256).hexdigest()

        assert gw.verify_signature(order_id, payment_id, expected_sig) is True

    def test_verify_signature_fail_on_tampered(self) -> None:
        """Tampered signature fails verification."""
        gw = _make_gateway()
        tampered_sig = "a" * 64
        assert gw.verify_signature("order_123", "pay_456", tampered_sig) is False


class TestRazorpayAmountValidation:
    """Tests for paise / INR conversion and amount verification."""

    def test_inr_to_paise(self) -> None:
        assert RazorpayGateway.inr_to_paise(Decimal("7.08")) == 708
        assert RazorpayGateway.inr_to_paise(Decimal("100.00")) == 10000
        assert RazorpayGateway.inr_to_paise(Decimal("1.50")) == 150

    def test_paise_to_inr(self) -> None:
        assert RazorpayGateway.paise_to_inr(708) == Decimal("7.08")
        assert RazorpayGateway.paise_to_inr(10000) == Decimal("100.00")

    def test_verify_amount_pass_on_match(self) -> None:
        gw = _make_gateway()
        # Should not raise exception
        gw.verify_amount(708, Decimal("7.08"))

    def test_verify_amount_fail_on_mismatch(self) -> None:
        from app.exceptions.base import PaymentAmountMismatchError
        gw = _make_gateway()
        with pytest.raises(PaymentAmountMismatchError):
            gw.verify_amount(708, Decimal("10.00"))

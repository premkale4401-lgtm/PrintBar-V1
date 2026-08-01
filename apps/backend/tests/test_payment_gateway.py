"""
PrintBar Backend — Payment Gateway Tests

Tests for Easebuzz HMAC-SHA512 signature generation and verification.
These are pure cryptographic tests — no DB or network required.
"""
from __future__ import annotations

import hashlib
from decimal import Decimal
from unittest.mock import patch

import pytest

from app.payments.easebuzz import EasebuzzGateway


def _make_gateway(key: str = "TESTKEY123", salt: str = "TESTSALT456") -> EasebuzzGateway:
    """Creates an EasebuzzGateway with test credentials."""
    with patch("app.payments.easebuzz.settings") as mock_settings:
        mock_settings.EASEBUZZ_KEY = key
        mock_settings.EASEBUZZ_SALT = salt
        mock_settings.EASEBUZZ_BASE_URL = "https://testpay.easebuzz.in"
        mock_settings.EASEBUZZ_ENV = "test"
        gw = EasebuzzGateway.__new__(EasebuzzGateway)
        gw._key = key
        gw._salt = salt
        gw._base_url = "https://testpay.easebuzz.in"
        gw._env = "test"
    return gw


class TestEasebuzzSignature:
    """Tests for HMAC-SHA512 hash generation and verification."""

    def test_initiation_hash_deterministic(self) -> None:
        """Same inputs always produce same hash."""
        gw = _make_gateway()
        h1 = gw.compute_initiation_hash("TXN001", "10.00", "Print", "Guest", "guest@test.com")
        h2 = gw.compute_initiation_hash("TXN001", "10.00", "Print", "Guest", "guest@test.com")
        assert h1 == h2
        assert len(h1) == 128  # SHA-512 hex = 128 chars

    def test_initiation_hash_changes_with_amount(self) -> None:
        gw = _make_gateway()
        h1 = gw.compute_initiation_hash("TXN001", "10.00", "Print", "Guest", "g@t.com")
        h2 = gw.compute_initiation_hash("TXN001", "20.00", "Print", "Guest", "g@t.com")
        assert h1 != h2

    def test_initiation_hash_changes_with_salt(self) -> None:
        gw1 = _make_gateway(salt="SALT_A")
        gw2 = _make_gateway(salt="SALT_B")
        h1 = gw1.compute_initiation_hash("TXN001", "10.00", "Print", "Guest", "g@t.com")
        h2 = gw2.compute_initiation_hash("TXN001", "10.00", "Print", "Guest", "g@t.com")
        assert h1 != h2

    def test_webhook_verification_correct_signature(self) -> None:
        """Correctly signed webhook should pass verification."""
        gw = _make_gateway(key="K123", salt="S456")

        # Build a webhook payload and compute the correct hash.
        payload = {
            "status": "success",
            "txnid": "JOB_UUID",
            "amount": "59.00",
            "productinfo": "Print",
            "firstname": "Guest",
            "email": "guest@test.com",
            "udf1": "PAY_UUID",
            "udf2": "", "udf3": "", "udf4": "", "udf5": "",
        }

        # Compute the correct reverse hash manually.
        reverse_str = (
            f"S456|{payload['status']}||"
            f"||||{payload['udf1']}|"
            f"{payload['email']}|{payload['firstname']}|{payload['productinfo']}|"
            f"{payload['amount']}|{payload['txnid']}|K123"
        )
        correct_hash = hashlib.sha512(reverse_str.encode()).hexdigest()
        payload["hash"] = correct_hash

        assert gw.verify_webhook_signature(payload) is True

    def test_webhook_verification_wrong_signature(self) -> None:
        """Tampered hash should fail verification."""
        gw = _make_gateway()
        payload = {
            "status": "success", "txnid": "JOB_UUID",
            "amount": "59.00", "productinfo": "Print",
            "firstname": "Guest", "email": "guest@test.com",
            "udf1": "", "udf2": "", "udf3": "", "udf4": "", "udf5": "",
            "hash": "deadbeef" * 16,  # Wrong hash
        }
        assert gw.verify_webhook_signature(payload) is False

    def test_amount_verification_passes_on_match(self) -> None:
        gw = _make_gateway()
        # Should not raise
        gw.verify_payment_amount("59.00", Decimal("59.00"))

    def test_amount_verification_fails_on_mismatch(self) -> None:
        from app.exceptions.base import PaymentAmountMismatchError
        gw = _make_gateway()
        with pytest.raises(PaymentAmountMismatchError):
            gw.verify_payment_amount("59.00", Decimal("60.00"))

    def test_amount_verification_fails_on_invalid_amount(self) -> None:
        from app.exceptions.base import PaymentAmountMismatchError
        gw = _make_gateway()
        with pytest.raises(PaymentAmountMismatchError):
            gw.verify_payment_amount("not_a_number", Decimal("59.00"))


class TestEasebuzzPayloadBuild:
    """Tests for payment payload construction."""

    def test_build_payload_contains_required_fields(self) -> None:
        gw = _make_gateway()
        payload = gw.build_payment_payload(
            txnid="TXN001",
            amount=Decimal("59.00"),
            productinfo="Print",
            firstname="Guest",
            email="guest@test.com",
            phone="9999999999",
            surl="https://api.printbar.in/payments/webhook",
            furl="https://api.printbar.in/payments/webhook",
        )
        required = ["key", "txnid", "amount", "productinfo", "firstname",
                    "email", "phone", "surl", "furl", "hash"]
        for field in required:
            assert field in payload, f"Missing field: {field}"

    def test_build_payload_amount_formatted_to_2dp(self) -> None:
        gw = _make_gateway()
        payload = gw.build_payment_payload(
            txnid="TXN001", amount=Decimal("59"), productinfo="Print",
            firstname="Guest", email="g@t.com", phone="9999999999",
            surl="https://x.com", furl="https://x.com",
        )
        assert payload["amount"] == "59.00"

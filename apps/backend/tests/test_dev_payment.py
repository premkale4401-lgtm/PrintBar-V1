"""
PrintBar Backend — Dev Payment & Webhook Endpoint Tests

Tests for:
1. Dev payment bypass endpoint (POST /api/v1/payments/dev/complete)
2. Razorpay webhook endpoint (POST /api/v1/payments/webhook/razorpay)
3. Cancel payment endpoint (POST /api/v1/payments/{job_id}/cancel)
"""
from __future__ import annotations

import hmac
import hashlib
import json
import pytest
from unittest.mock import patch, AsyncMock

from app.core.config import get_settings


@pytest.mark.asyncio
async def test_dev_complete_payment_requires_auth(async_client) -> None:
    """POST /api/v1/payments/dev/complete without auth token returns 401."""
    response = await async_client.post("/api/v1/payments/dev/complete?job_id=00000000-0000-0000-0000-000000000001")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_webhook_invalid_signature(async_client) -> None:
    """
    POST /api/v1/payments/webhook/razorpay with invalid HMAC.

    In mock payment mode: returns 404 (webhook not applicable).
    In razorpay mode: returns 400 with PAY_001 error code.
    """
    settings = get_settings()
    response = await async_client.post(
        "/api/v1/payments/webhook/razorpay",
        content=b'{"event":"payment.captured"}',
        headers={"X-Razorpay-Signature": "invalid_signature"},
    )

    if settings.is_mock_payment:
        # Mock provider: webhook endpoint returns 404 — not applicable.
        assert response.status_code == 404
        body = response.json()
        assert body["success"] is False
        assert body["error"]["code"] == "PAY_007"
    else:
        # Real provider: invalid signature → 400.
        assert response.status_code == 400
        body = response.json()
        assert body["success"] is False
        assert body["error"]["code"] == "PAY_001"


@pytest.mark.asyncio
async def test_cancel_payment_requires_auth(async_client) -> None:
    """POST /api/v1/payments/{job_id}/cancel without auth returns 401."""
    response = await async_client.post("/api/v1/payments/00000000-0000-0000-0000-000000000001/cancel")
    assert response.status_code == 401


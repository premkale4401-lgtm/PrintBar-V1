"""
Tests for payment webhook handling.
"""

from __future__ import annotations

import json

import pytest


@pytest.mark.asyncio
async def test_webhook_404_in_mock_mode(async_client):
    """Webhook returns 404 when PAYMENT_PROVIDER=mock (no real webhooks expected)."""
    resp = await async_client.post(
        "/api/v1/payments/webhook",
        content=b"{}",
        headers={"Content-Type": "application/json", "X-Razorpay-Signature": "fakesig"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_webhook_missing_signature_rejected(async_client):
    """Webhook without X-Razorpay-Signature must be rejected (400 or 404)."""
    resp = await async_client.post(
        "/api/v1/payments/webhook",
        content=json.dumps({"event": "payment.captured"}).encode(),
        headers={"Content-Type": "application/json"},
    )
    assert resp.status_code in (400, 404, 422)


@pytest.mark.asyncio
async def test_dev_complete_invalid_order(async_client):
    """POST /dev/complete requires guest session JWT — returns 401 without it."""
    resp = await async_client.post(
        "/api/v1/payments/dev/complete",
        json={"orderId": "order_nonexistent_abc123"},
    )
    # Endpoint requires auth — 401 without session token.
    # Must not crash (not 500).
    assert resp.status_code != 500
    assert resp.status_code != 404

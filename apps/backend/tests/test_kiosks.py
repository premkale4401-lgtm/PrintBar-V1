"""
Tests for kiosk HTTP management endpoints.
"""
from __future__ import annotations
import pytest


@pytest.mark.asyncio
async def test_kiosk_register_requires_auth(async_client):
    """POST /kiosks/register requires admin JWT."""
    resp = await async_client.post(
        "/api/v1/kiosks/register",
        json={"name": "Test Kiosk", "location": "Building A", "city": "Mumbai"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_kiosk_auth_invalid_credentials(async_client):
    """POST /kiosks/auth with wrong API key returns 401."""
    import uuid
    resp = await async_client.post(
        "/api/v1/kiosks/auth",
        json={"kiosk_id": str(uuid.uuid4()), "api_key": "a" * 64},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_kiosk_auth_invalid_uuid_format(async_client):
    """POST /kiosks/auth with non-UUID kiosk_id returns 422."""
    resp = await async_client.post(
        "/api/v1/kiosks/auth",
        json={"kiosk_id": "not-a-uuid", "api_key": "a" * 64},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_kiosk_heartbeat_nonexistent_kiosk(async_client):
    """POST /kiosks/heartbeat with unknown kiosk_id returns 404."""
    import uuid
    resp = await async_client.post(
        "/api/v1/kiosks/heartbeat",
        json={"kiosk_id": str(uuid.uuid4())},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_kiosk_detail_requires_auth(async_client):
    """GET /kiosks/{id} requires admin JWT."""
    import uuid
    resp = await async_client.get(f"/api/v1/kiosks/{uuid.uuid4()}")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_printer_detail_requires_auth(async_client):
    """GET /printers/{id} requires admin JWT."""
    import uuid
    resp = await async_client.get(f"/api/v1/printers/{uuid.uuid4()}")
    assert resp.status_code == 401

"""
PrintBar Backend — Comprehensive Admin API Tests

Tests for all admin endpoints including new endpoints added in the
final production release:
    - GET  /admin/dashboard
    - GET  /admin/jobs
    - GET  /admin/kiosks
    - GET  /admin/kiosks/{id}
    - POST /admin/kiosks
    - GET  /admin/pricing
    - POST /admin/pricing
    - GET  /admin/audit-logs
    - GET  /admin/users
"""
from __future__ import annotations

import pytest

# ─── Auth Guard Tests ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_admin_dashboard_requires_auth(async_client):
    """GET /admin/dashboard must return 401 without a valid JWT."""
    resp = await async_client.get("/api/v1/admin/dashboard")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_admin_kiosks_list_requires_auth(async_client):
    """GET /admin/kiosks must return 401 without auth."""
    resp = await async_client.get("/api/v1/admin/kiosks")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_admin_kiosk_detail_requires_auth(async_client):
    """GET /admin/kiosks/{id} must return 401 without auth."""
    import uuid
    resp = await async_client.get(f"/api/v1/admin/kiosks/{uuid.uuid4()}")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_admin_jobs_list_requires_auth(async_client):
    """GET /admin/jobs must return 401 without auth."""
    resp = await async_client.get("/api/v1/admin/jobs")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_admin_pricing_list_requires_auth(async_client):
    """GET /admin/pricing must return 401 without auth."""
    resp = await async_client.get("/api/v1/admin/pricing")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_admin_pricing_create_requires_auth(async_client):
    """POST /admin/pricing must return 401 without auth."""
    resp = await async_client.post(
        "/api/v1/admin/pricing",
        json={"name": "Test", "bwPriceInr": "2.00", "colorPriceInr": "10.00"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_admin_audit_logs_requires_auth(async_client):
    """GET /admin/audit-logs must return 401 without auth."""
    resp = await async_client.get("/api/v1/admin/audit-logs")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_admin_users_requires_auth(async_client):
    """GET /admin/users must return 401 without auth."""
    resp = await async_client.get("/api/v1/admin/users")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_admin_login_invalid_credentials(async_client):
    """POST /admin/auth/login with bad credentials must return 401."""
    resp = await async_client.post(
        "/api/v1/admin/auth/login",
        json={"email": "nobody@example.com", "password": "wrongpassword"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_system_status_requires_auth(async_client):
    """GET /system/status must return 401 without auth."""
    resp = await async_client.get("/api/v1/system/status")
    assert resp.status_code == 401


# ─── Create Kiosk Request Validation ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_kiosk_requires_super_admin(async_client):
    """POST /admin/kiosks must return 401 without auth (not 422)."""
    resp = await async_client.post(
        "/api/v1/admin/kiosks",
        json={"name": "Test Kiosk", "location": "Test Location"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_admin_kiosk_rotate_key_requires_auth(async_client):
    """POST /admin/kiosks/{id}/rotate-key must return 401 without auth."""
    import uuid
    resp = await async_client.post(f"/api/v1/admin/kiosks/{uuid.uuid4()}/rotate-key")
    assert resp.status_code == 401


# ─── Response Structure Tests (unauthenticated → 401 with proper error schema) ─

@pytest.mark.asyncio
async def test_admin_401_response_structure(async_client):
    """401 responses from admin endpoints must use the PrintBar error schema."""
    resp = await async_client.get("/api/v1/admin/dashboard")
    assert resp.status_code == 401
    # PrintBar uses a custom error schema: {success, error: {code, message}, requestId}
    body = resp.json()
    assert body["success"] is False
    assert "error" in body
    assert "code" in body["error"]
    assert "message" in body["error"]


# ─── Jobs Endpoint Pagination Validation ─────────────────────────────────────

@pytest.mark.asyncio
async def test_admin_jobs_invalid_page_param_rejected(async_client):
    """GET /admin/jobs with page=0 should be rejected with 401 (auth before validation)."""
    resp = await async_client.get("/api/v1/admin/jobs?page=0")
    # Auth check happens before query validation in FastAPI.
    assert resp.status_code == 401


# ─── Pricing Endpoint Validation ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_pricing_calculate_endpoint_is_accessible(async_client):
    """
    GET /api/v1/pricing/calculate must return 200 (public endpoint, no auth).
    Accepts either success:True (rule found) or PRICE_500 (no rule seeded).
    """
    resp = await async_client.get(
        "/api/v1/pricing/calculate",
        params={"pages": 5, "color_mode": "BW", "paper_size": "A4", "copies": 1},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "success" in data
    assert "data" in data or "error" in data

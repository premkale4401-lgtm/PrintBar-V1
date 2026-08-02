"""
Tests for admin API endpoints.
"""
from __future__ import annotations
from unittest.mock import AsyncMock, patch
import pytest


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
async def test_admin_jobs_list_requires_auth(async_client):
    """GET /admin/jobs must return 401 without auth."""
    resp = await async_client.get("/api/v1/admin/jobs")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_admin_pricing_requires_auth(async_client):
    """GET /admin/pricing must return 401 without auth."""
    resp = await async_client.get("/api/v1/admin/pricing")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_admin_audit_logs_requires_auth(async_client):
    """GET /admin/audit-logs must return 401 without auth."""
    resp = await async_client.get("/api/v1/admin/audit-logs")
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


@pytest.mark.asyncio
async def test_printers_list_requires_auth(async_client):
    """GET /printers must return 401 without auth."""
    resp = await async_client.get("/api/v1/printers")
    assert resp.status_code == 401

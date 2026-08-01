"""
PrintBar Backend — Health Endpoint Tests

Tests for GET /health, GET /live, and GET /ready endpoints.

All tests are integration tests using the async httpx client
against the full FastAPI application stack.
"""

import pytest


@pytest.mark.asyncio
async def test_health_returns_200(async_client) -> None:
    """GET /health must return HTTP 200 with {"status": "healthy"}."""
    response = await async_client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "healthy"


@pytest.mark.asyncio
async def test_health_has_request_id_header(async_client) -> None:
    """Every response must include the X-Request-ID header."""
    response = await async_client.get("/health")
    assert "x-request-id" in response.headers


@pytest.mark.asyncio
async def test_live_returns_200(async_client) -> None:
    """GET /live must return HTTP 200."""
    response = await async_client.get("/live")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "alive"


@pytest.mark.asyncio
async def test_ready_returns_json(async_client) -> None:
    """
    GET /ready must return a JSON response with a 'checks' object.

    The ready endpoint may return 200 or 503 depending on whether test
    infrastructure is available. We only assert the response shape.
    """
    response = await async_client.get("/ready")
    assert response.status_code in (200, 503)
    body = response.json()
    assert "status" in body
    assert "checks" in body
    assert isinstance(body["checks"], dict)


@pytest.mark.asyncio
async def test_ready_includes_database_check(async_client) -> None:
    """GET /ready must include a 'database' key in checks."""
    response = await async_client.get("/ready")
    body = response.json()
    assert "database" in body["checks"]


@pytest.mark.asyncio
async def test_ready_includes_redis_check(async_client) -> None:
    """GET /ready must include a 'redis' key in checks."""
    response = await async_client.get("/ready")
    body = response.json()
    assert "redis" in body["checks"]


@pytest.mark.asyncio
async def test_ready_includes_storage_check(async_client) -> None:
    """GET /ready must include a 'storage' key in checks."""
    response = await async_client.get("/ready")
    body = response.json()
    assert "storage" in body["checks"]


@pytest.mark.asyncio
async def test_response_has_security_headers(async_client) -> None:
    """Every response must include mandatory security headers per doc 07."""
    response = await async_client.get("/health")
    headers = response.headers
    assert "x-content-type-options" in headers
    assert "x-frame-options" in headers
    assert "referrer-policy" in headers


@pytest.mark.asyncio
async def test_unknown_route_returns_404(async_client) -> None:
    """Unknown routes must return a structured 404 error response."""
    response = await async_client.get("/api/v1/nonexistent")
    assert response.status_code == 404
    body = response.json()
    assert body["success"] is False
    assert "error" in body
    assert "code" in body["error"]
    assert "message" in body["error"]

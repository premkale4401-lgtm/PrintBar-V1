"""
PrintBar Backend — Session API Tests

Tests for POST /api/v1/sessions and DELETE /api/v1/sessions/me.
"""

import pytest


@pytest.mark.asyncio
async def test_create_session_returns_201(async_client) -> None:
    """POST /api/v1/sessions must return 201 with an access token."""
    response = await async_client.post("/api/v1/sessions")
    assert response.status_code == 201
    body = response.json()
    assert body["success"] is True
    data = body["data"]
    assert "sessionId" in data
    assert "accessToken" in data
    assert "expiresAt" in data
    assert "createdAt" in data


@pytest.mark.asyncio
async def test_create_session_token_is_jwt(async_client) -> None:
    """The returned access token must be a valid JWT with 3 parts."""
    response = await async_client.post("/api/v1/sessions")
    token = response.json()["data"]["accessToken"]
    parts = token.split(".")
    assert len(parts) == 3, "Access token must be a JWT (header.payload.signature)"


@pytest.mark.asyncio
async def test_create_session_has_request_id(async_client) -> None:
    """Every response must include X-Request-ID."""
    response = await async_client.post("/api/v1/sessions")
    assert "x-request-id" in response.headers


@pytest.mark.asyncio
async def test_delete_session_requires_auth(async_client) -> None:
    """DELETE /api/v1/sessions/me without a token must return 401."""
    response = await async_client.delete("/api/v1/sessions/me")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_delete_session_with_valid_token(async_client) -> None:
    """DELETE /api/v1/sessions/me with a valid token must return 200."""
    # Create a session first.
    create_response = await async_client.post("/api/v1/sessions")
    token = create_response.json()["data"]["accessToken"]

    response = await async_client.delete(
        "/api/v1/sessions/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["success"] is True


@pytest.mark.asyncio
async def test_delete_session_with_invalid_token(async_client) -> None:
    """DELETE /api/v1/sessions/me with an invalid token must return 401."""
    response = await async_client.delete(
        "/api/v1/sessions/me",
        headers={"Authorization": "Bearer invalid.token.here"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_session_token_can_access_uploads_endpoint(async_client) -> None:
    """A session token from POST /sessions should be accepted by the upload endpoint."""
    create_response = await async_client.post("/api/v1/sessions")
    token = create_response.json()["data"]["accessToken"]

    # Send a request with no file — should get 422 (validation error), not 401.
    response = await async_client.post(
        "/api/v1/uploads",
        headers={"Authorization": f"Bearer {token}"},
    )
    # 422 means we authenticated successfully but the request body is invalid.
    assert response.status_code in (
        422,
        400,
    ), f"Expected 422 (auth OK, missing file) but got {response.status_code}"


@pytest.mark.asyncio
async def test_upload_endpoint_rejects_no_token(async_client) -> None:
    """Upload endpoint must reject requests with no session token."""
    response = await async_client.post("/api/v1/uploads")
    assert response.status_code == 401

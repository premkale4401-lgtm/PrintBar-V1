"""
PrintBar Backend — Storage Service Unit Tests

Tests for the StorageService class including:
    - SHA-256 checksum computation
    - Object path generation
    - Retry logic behavior (mocked network)
    - Error handling
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.storage.service import SupabaseStorageService

# ─── Static Method Tests ──────────────────────────────────────────────────────


def test_compute_sha256_returns_hex_string():
    """SHA-256 of known bytes must produce a 64-char hex string."""
    data = b"hello world"
    result = SupabaseStorageService.compute_sha256(data)
    assert isinstance(result, str)
    assert len(result) == 64  # SHA-256 produces 32 bytes = 64 hex chars
    # Verify against known correct hash for "hello world".
    assert result == "b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9"


def test_compute_sha256_empty_bytes():
    """SHA-256 of empty bytes must return the known SHA-256 of empty string."""
    result = SupabaseStorageService.compute_sha256(b"")
    assert result == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"


def test_build_object_path_format():
    """build_object_path must produce a path matching the expected format."""
    session_id = "abc12345-test-session"
    file_id = "f47ac10b-58cc-4372-a567-0e02b2c3d479"
    path = SupabaseStorageService.build_object_path(session_id, file_id)

    parts = path.split("/")
    assert len(parts) == 4
    # Year (4 digits), Month (2 digits), session prefix (8 chars), file_id.pdf
    assert len(parts[0]) == 4 and parts[0].isdigit()  # year
    assert len(parts[1]) == 2 and parts[1].isdigit()  # month (zero-padded)
    assert parts[2] == "abc12345"  # first 8 chars of session_id
    assert parts[3] == f"{file_id}.pdf"


def test_build_object_path_truncates_session_id():
    """Session ID longer than 8 chars must be truncated to 8 in the path."""
    path = SupabaseStorageService.build_object_path("abcdefghijklmnop", "file-id-here")
    assert "/abcdefgh/" in path


# ─── Upload Retry Logic Tests ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_upload_file_success_first_attempt():
    """upload_file must return the full path on a successful first attempt."""
    mock_response = MagicMock()
    mock_response.status_code = 201

    service = SupabaseStorageService()
    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client_class.return_value = mock_client

        result = await service.upload_file(
            bucket="print-files",
            object_path="2026/08/test/file.pdf",
            file_data=b"%PDF-1.4 test",
        )

    assert result == "print-files/2026/08/test/file.pdf"


@pytest.mark.asyncio
async def test_upload_file_raises_on_permanent_4xx():
    """upload_file must raise StorageError immediately on a 4xx response (no retry)."""
    from app.exceptions.base import StorageError

    mock_response = MagicMock()
    mock_response.status_code = 400
    mock_response.text = "Bad Request"

    service = SupabaseStorageService()
    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client_class.return_value = mock_client

        with pytest.raises(StorageError, match="Upload rejected"):
            await service.upload_file(
                bucket="print-files",
                object_path="2026/08/test/file.pdf",
                file_data=b"%PDF-1.4 test",
            )


# ─── Signed URL Tests ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_signed_url_raises_when_url_missing():
    """create_signed_url must raise StorageError when response has no signedURL field."""
    from app.exceptions.base import StorageError

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json = MagicMock(return_value={"error": "no url here"})

    service = SupabaseStorageService()
    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client_class.return_value = mock_client

        with pytest.raises(StorageError, match="Signed URL missing"):
            await service.create_signed_url(
                bucket="print-files",
                object_path="2026/08/test/file.pdf",
            )


@pytest.mark.asyncio
@patch("app.storage.service.settings.SUPABASE_URL", "https://supabase.example.com")
async def test_create_signed_url_prepends_base_url_for_relative_path():
    """create_signed_url must prepend SUPABASE_URL to relative signed URLs."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json = MagicMock(
        return_value={"signedURL": "/storage/v1/object/sign/bucket/path?token=abc"}
    )

    service = SupabaseStorageService()
    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client_class.return_value = mock_client

        result = await service.create_signed_url(
            bucket="print-files",
            object_path="2026/08/test/file.pdf",
        )

    # Must be an absolute URL.
    assert result.startswith("http")


# ─── Delete Tests ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_delete_file_returns_false_on_404():
    """delete_file must return False when file is not found (idempotent delete)."""
    mock_response = MagicMock()
    mock_response.status_code = 404

    service = SupabaseStorageService()
    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.delete = AsyncMock(return_value=mock_response)
        mock_client_class.return_value = mock_client

        result = await service.delete_file("print-files", "2026/08/test/file.pdf")

    assert result is False


@pytest.mark.asyncio
async def test_delete_file_returns_true_on_success():
    """delete_file must return True when file is deleted successfully."""
    mock_response = MagicMock()
    mock_response.status_code = 200

    service = SupabaseStorageService()
    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.delete = AsyncMock(return_value=mock_response)
        mock_client_class.return_value = mock_client

        result = await service.delete_file("print-files", "2026/08/test/file.pdf")

    assert result is True

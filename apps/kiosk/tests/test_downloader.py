"""
Tests for kiosk agent job downloader.
"""

from __future__ import annotations
import hashlib
import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))


def make_settings(tmp_path):
    from app.config.settings import KioskSettings

    return KioskSettings(
        kiosk_id="test-kiosk",
        api_key="test-key",
        temp_dir=str(tmp_path),
        download_timeout_sec=10,
    )


@pytest.mark.asyncio
async def test_download_success(tmp_path):
    """Downloader saves the file and returns the path."""
    from app.jobs.downloader import JobDownloader

    content = b"%PDF-1.4 fake pdf content"
    sha256 = hashlib.sha256(content).hexdigest()
    settings = make_settings(tmp_path)
    downloader = JobDownloader(settings)

    mock_response = AsyncMock()
    mock_response.raise_for_status = MagicMock()

    async def _aiter_bytes(chunk_size=65536):
        yield content

    mock_response.aiter_bytes = _aiter_bytes

    mock_cm = AsyncMock()
    mock_cm.__aenter__ = AsyncMock(return_value=mock_response)
    mock_cm.__aexit__ = AsyncMock(return_value=False)

    mock_client = AsyncMock()
    mock_client.stream = MagicMock(return_value=mock_cm)

    mock_client_cm = AsyncMock()
    mock_client_cm.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client_cm.__aexit__ = AsyncMock(return_value=False)

    with patch("httpx.AsyncClient", return_value=mock_client_cm):
        path = await downloader.download(
            "job-001", "https://example.com/file.pdf", sha256
        )

    assert os.path.exists(path)
    assert path.endswith("job-001.pdf")


@pytest.mark.asyncio
async def test_download_sha256_mismatch_raises(tmp_path):
    """Downloader raises RuntimeError if SHA-256 does not match."""
    from app.jobs.downloader import JobDownloader

    content = b"%PDF-1.4 fake pdf content"
    wrong_sha = "a" * 64  # wrong hash

    settings = make_settings(tmp_path)
    downloader = JobDownloader(settings)

    mock_response = AsyncMock()
    mock_response.raise_for_status = MagicMock()

    async def _aiter_bytes(chunk_size=65536):
        yield content

    mock_response.aiter_bytes = _aiter_bytes
    mock_cm = AsyncMock()
    mock_cm.__aenter__ = AsyncMock(return_value=mock_response)
    mock_cm.__aexit__ = AsyncMock(return_value=False)
    mock_client = AsyncMock()
    mock_client.stream = MagicMock(return_value=mock_cm)
    mock_client_cm = AsyncMock()
    mock_client_cm.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client_cm.__aexit__ = AsyncMock(return_value=False)

    with patch("httpx.AsyncClient", return_value=mock_client_cm):
        with pytest.raises(RuntimeError, match="SHA-256 mismatch"):
            await downloader.download(
                "job-002", "https://example.com/file.pdf", wrong_sha
            )

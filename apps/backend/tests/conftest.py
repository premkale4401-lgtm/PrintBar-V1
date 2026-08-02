"""
PrintBar Backend — Test Configuration (pytest conftest)

Provides shared fixtures for all tests:
    - async_client: HTTPX async test client with an in-memory SQLite DB
    - db_session:   AsyncSession for direct DB access in tests
    - mock_settings: Override settings for specific tests
"""
from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database.base import Base
from app.database.session import get_db
from app.main import app

import os

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "sqlite+aiosqlite:///printbar.db",
)

_test_engine = create_async_engine(
    TEST_DATABASE_URL,
    pool_pre_ping=True,
)
_TestSessionFactory = async_sessionmaker(
    bind=_test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)



@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_test_database():
    """Session fixture for test database setup and teardown."""
    yield
    await _test_engine.dispose()


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Provides a test database session that rolls back after each test."""
    async with _TestSessionFactory() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def async_client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """
    Provides an HTTPX async test client connected to the FastAPI app.

    DB dependency is overridden to use the test SQLite session.
    Background workers are suppressed during tests.
    """
    async def _override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db

    # Suppress background workers in tests.
    with patch("app.workers.background.start_all_workers", new_callable=AsyncMock):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            yield client

    app.dependency_overrides.clear()


@pytest.fixture
def mock_storage():
    """Mocks Supabase Storage to prevent real network calls in tests."""
    with (
        patch(
            "app.storage.service.StorageService.upload_file",
            new_callable=AsyncMock,
            return_value="print-files/test/path.pdf",
        ),
        patch(
            "app.storage.service.StorageService.delete_file",
            new_callable=AsyncMock,
            return_value=True,
        ),
        patch(
            "app.storage.service.StorageService.create_signed_url",
            new_callable=AsyncMock,
            return_value="https://supabase.example.com/signed-url",
        ),
    ) as mocks:
        yield mocks

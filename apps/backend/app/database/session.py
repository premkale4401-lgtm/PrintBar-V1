"""
PrintBar Backend — Async Database Session Factory

Provides SQLAlchemy async engine, session factory, and FastAPI dependency
for database access throughout the application.

Usage (in route handlers):
    from app.database.session import get_db
    
    @router.get("/example")
    async def example(db: AsyncSession = Depends(get_db)):
        result = await db.execute(select(SomeModel))
        ...

Usage (in tests):
    from app.database.session import engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_settings = get_settings()


def _create_engine() -> AsyncEngine:
    """
    Creates the SQLAlchemy async engine with production-ready pool settings.

    Returns:
        Configured AsyncEngine instance.
    """
    if "sqlite" in _settings.DATABASE_URL:
        return create_async_engine(
            _settings.DATABASE_URL,
            echo=_settings.DATABASE_ECHO,
        )
    return create_async_engine(
        _settings.DATABASE_URL,
        echo=_settings.DATABASE_ECHO,
        pool_size=_settings.DATABASE_POOL_SIZE,
        max_overflow=_settings.DATABASE_MAX_OVERFLOW,
        pool_timeout=_settings.DATABASE_POOL_TIMEOUT,
        pool_pre_ping=True,  # Validate connections before use.
        pool_recycle=3600,   # Recycle connections after 1 hour.
    )


engine: AsyncEngine = _create_engine()

AsyncSessionFactory: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,  # Prevents lazy-loading after commit in async context.
    autocommit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency that provides a database session for each request.

    The session is automatically committed on success and rolled back on error.
    Never import this directly into controllers; use FastAPI's Depends().

    Yields:
        AsyncSession: Active database session scoped to the current request.
    """
    session: AsyncSession = AsyncSessionFactory()
    try:
        yield session
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


async def check_database_connectivity() -> bool:
    """
    Verifies that the database is reachable.

    Used by the /ready health endpoint to confirm database availability.

    Returns:
        True if the database responds, False on error.
    """
    try:
        from sqlalchemy import select, text
        from app.database.base import Base

        async with AsyncSessionFactory() as session:
            await session.execute(text("SELECT 1"))

            # Verify that all required schema objects (tables) are present.
            for table in Base.metadata.sorted_tables:
                await session.execute(select(1).select_from(table).limit(1))

        return True
    except Exception as exc:
        logger.error("database_connectivity_failed", error=str(exc))
        return False

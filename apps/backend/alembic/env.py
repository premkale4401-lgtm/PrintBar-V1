"""
PrintBar Backend — Alembic Migration Environment

Configures Alembic for async SQLAlchemy migrations.
The DATABASE_URL is always read from the environment variable.
No connection strings are hardcoded.

This file is required by Alembic and must not be edited without
understanding the async migration pattern.
"""

import asyncio
import os
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

import app.models  # noqa: F401 — registers all 13 models with metadata
from alembic import context

# Import ALL models so Alembic can detect changes for autogenerate.
# This is the authoritative model import for migrations.
from app.database.base import Base  # noqa: F401

config = context.config

# Override the sqlalchemy.url with the environment variable or defaults.
from app.core.config import get_settings
database_url = os.environ.get("DATABASE_URL") or get_settings().DATABASE_URL

if not database_url:
    raise RuntimeError("DATABASE_URL environment variable is required for migrations.")

# Alembic requires a synchronous URL format for configuration;
# the async engine handles the async execution below.
config.set_main_option(
    "sqlalchemy.url",
    database_url.replace("postgresql+asyncpg://", "postgresql://"),
)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """
    Run migrations in 'offline' mode.

    Generates SQL scripts without connecting to the database.
    Useful for reviewing migrations before applying them.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):  # type: ignore[no-untyped-def]
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """
    Run migrations asynchronously using the asyncpg driver.

    Alembic does not natively support async engines,
    so we use run_sync to execute migrations synchronously
    inside an async context.
    """
    configuration = config.get_section(config.config_ini_section) or {}
    configuration["sqlalchemy.url"] = database_url  # type: ignore[index]

    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """
    Run migrations in 'online' mode with a live database connection.
    """
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

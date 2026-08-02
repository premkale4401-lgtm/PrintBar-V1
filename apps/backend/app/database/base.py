"""
PrintBar Backend — SQLAlchemy Declarative Base

All SQLAlchemy models inherit from this Base.
Every model uses UUID v4 primary keys and includes created_at/updated_at timestamps.

Usage:
    from app.database.base import Base, TimestampMixin, UUIDMixin
"""

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import DateTime, Uuid, func, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """
    SQLAlchemy declarative base for all PrintBar models.

    Provides:
        - Type annotation map for Mapped columns.
        - Common __repr__ for debugging.
    """

    type_annotation_map: dict[Any, Any] = {}

    def __repr__(self) -> str:
        pk = getattr(self, "id", None)
        return f"<{self.__class__.__name__} id={pk}>"


class UUIDMixin:
    """
    Provides a UUID v4 primary key for every model.

    UUID primary keys are required per the database design specification
    to avoid information leakage through sequential IDs.
    """

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )


class TimestampMixin:
    """
    Provides created_at and updated_at timestamps on every model.

    - created_at: Set once at insert time by the database.
    - updated_at: Automatically updated by the database on every UPDATE.

    All timestamps are stored in UTC.
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class PrintBarBase(Base, UUIDMixin, TimestampMixin):
    """
    Abstract base class combining Base, UUID primary key, and timestamps.

    All concrete PrintBar entities should inherit from this class.
    Audit logs and webhook history should NOT use TimestampMixin's
    updated_at, since they are immutable records.
    """

    __abstract__ = True

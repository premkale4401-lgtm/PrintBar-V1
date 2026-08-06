"""
PrintBar Backend — User Repository

Data access layer for User (admin) records.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.user import User

logger = get_logger(__name__)


class UserRepository:
    """Repository for User (admin) records."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_by_id(self, user_id: uuid.UUID) -> User | None:
        """Returns a user by primary key."""
        result = await self._db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> User | None:
        """Returns a user by email address (case-insensitive)."""
        result = await self._db.execute(select(User).where(User.email == email.lower().strip()))
        return result.scalar_one_or_none()

    async def get_all_active(self) -> list[User]:
        """Returns all active admin users."""
        result = await self._db.execute(
            select(User).where(User.is_active.is_(True)).order_by(User.name)
        )
        return list(result.scalars().all())

    async def create(self, *, email: str, name: str, password_hash: str, role: str) -> User:
        """Creates a new admin user record."""
        user = User(email=email.lower().strip(), name=name, password_hash=password_hash, role=role)
        self._db.add(user)
        await self._db.flush()
        logger.info("user_created", user_id=str(user.id), email=email, role=role)
        return user

    async def update_last_login(self, user_id: uuid.UUID, timestamp: str) -> None:
        """Updates the last_login_at timestamp."""
        from sqlalchemy import update

        await self._db.execute(
            update(User).where(User.id == user_id).values(last_login_at=timestamp)
        )

    async def deactivate(self, user_id: uuid.UUID) -> None:
        """Soft-deletes a user account."""
        from sqlalchemy import update

        await self._db.execute(update(User).where(User.id == user_id).values(is_active=False))
        logger.info("user_deactivated", user_id=str(user_id))

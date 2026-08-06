"""
PrintBar Backend — Heartbeat Log Repository

Data access for HeartbeatLog records.
Auto-cleanup removes entries older than 30 days.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.heartbeat_log import HeartbeatLog

logger = get_logger(__name__)


class HeartbeatLogRepository:
    """Repository for HeartbeatLog records."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def create(self, *, kiosk_id: uuid.UUID, **kwargs) -> HeartbeatLog:
        """Appends a new heartbeat log entry."""
        log = HeartbeatLog(kiosk_id=kiosk_id, **kwargs)
        self._db.add(log)
        await self._db.flush()
        return log

    async def get_recent_by_kiosk(self, kiosk_id: uuid.UUID, limit: int = 50) -> list[HeartbeatLog]:
        """Returns the most recent heartbeat logs for a kiosk."""
        result = await self._db.execute(
            select(HeartbeatLog)
            .where(HeartbeatLog.kiosk_id == kiosk_id)
            .order_by(HeartbeatLog.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def cleanup_old(self, days: int = 30) -> int:
        """Deletes heartbeat logs older than the specified number of days. Returns count deleted."""
        cutoff = (datetime.now(tz=UTC) - timedelta(days=days)).isoformat()
        result = await self._db.execute(
            delete(HeartbeatLog).where(HeartbeatLog.created_at < cutoff)
        )
        count = result.rowcount
        if count:
            logger.info("heartbeat_logs_cleaned", count=count, days=days)
        return count

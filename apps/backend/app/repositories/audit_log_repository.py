"""
PrintBar Backend — Audit Log Repository

Append-only data access for AuditLog records.
Records are NEVER updated or deleted.
"""
from __future__ import annotations
import uuid
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.logging import get_logger
from app.models.audit_log import AuditLog

logger = get_logger(__name__)

class AuditLogRepository:
    """Append-only repository for AuditLog records."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def create(
        self,
        *,
        action: str,
        actor_type: str = "SYSTEM",
        actor_user_id: uuid.UUID | None = None,
        actor_kiosk_id: uuid.UUID | None = None,
        entity_type: str | None = None,
        entity_id: str | None = None,
        print_job_id: uuid.UUID | None = None,
        ip_address: str | None = None,
        result: str = "SUCCESS",
        details: str | None = None,
        error: str | None = None,
    ) -> AuditLog:
        """Creates a new immutable audit log entry."""
        entry = AuditLog(
            action=action,
            actor_type=actor_type,
            actor_user_id=actor_user_id,
            actor_kiosk_id=actor_kiosk_id,
            entity_type=entity_type,
            entity_id=entity_id,
            print_job_id=print_job_id,
            ip_address=ip_address,
            result=result,
            details=details,
            error=error,
        )
        self._db.add(entry)
        await self._db.flush()
        return entry

    async def list_paginated(self, *, limit: int = 50, offset: int = 0) -> tuple[list[AuditLog], int]:
        """Returns a page of audit log entries, newest first."""
        total_result = await self._db.execute(select(func.count(AuditLog.id)))
        total = total_result.scalar() or 0
        result = await self._db.execute(
            select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit).offset(offset)
        )
        return list(result.scalars().all()), total

    async def list_by_entity(self, entity_type: str, entity_id: str) -> list[AuditLog]:
        """Returns all audit log entries for a specific entity."""
        result = await self._db.execute(
            select(AuditLog)
            .where(AuditLog.entity_type == entity_type, AuditLog.entity_id == entity_id)
            .order_by(AuditLog.created_at.desc())
        )
        return list(result.scalars().all())

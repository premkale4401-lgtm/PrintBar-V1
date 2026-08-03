"""
PrintBar Backend — Kiosk Service

Business logic for kiosk lifecycle management.
All DB operations are delegated to KioskRepository.
"""
from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.core.security import jwt_handler
from app.models.kiosk import Kiosk
from app.repositories.kiosk_repository import KioskRepository

logger = get_logger(__name__)


class KioskService:
    """Encapsulates all kiosk business logic."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._repo = KioskRepository(db)

    async def register_kiosk(
        self, *, name: str, location: str, city: str,
        notes: str | None = None, latitude: float | None = None, longitude: float | None = None,
        admin_id: str,
    ) -> tuple[Kiosk, str]:
        """
        Provisions a new kiosk.

        Returns:
            Tuple of (Kiosk record, raw API key). Raw key shown once.
        """
        kiosk, raw_key = await self._repo.create(
            name=name, location=location, city=city,
            notes=notes, latitude=latitude, longitude=longitude,
        )
        await self._db.commit()
        await self._db.refresh(kiosk)
        logger.info("kiosk_service_registered", kiosk_id=str(kiosk.id), admin_id=admin_id)
        return kiosk, raw_key

    async def authenticate_kiosk(self, *, kiosk_id: str, api_key: str) -> str | None:
        """
        Authenticates a kiosk via API key and returns a JWT.

        Returns:
            JWT string, or None if authentication fails.
        """
        try:
            kiosk_uuid = uuid.UUID(kiosk_id)
        except ValueError:
            return None

        key_hash = KioskRepository.hash_api_key(api_key)
        kiosk = await self._repo.get_by_api_key_hash(key_hash)
        if kiosk is None or kiosk.id != kiosk_uuid:
            logger.warning("kiosk_service_auth_failed", kiosk_id=kiosk_id)
            return None

        token = jwt_handler.create_access_token(
            subject=str(kiosk.id), role="KIOSK", extra_claims={"name": kiosk.name}
        )
        logger.info("kiosk_service_authenticated", kiosk_id=str(kiosk.id))
        return token

    async def get_kiosk_detail(self, kiosk_id: uuid.UUID) -> Kiosk | None:
        """Returns the full kiosk record, or None if not found."""
        return await self._repo.get_by_id(kiosk_id)

    async def get_all_active(self) -> list[Kiosk]:
        """Returns all active kiosks."""
        return await self._repo.get_all_active()

    async def set_maintenance_mode(self, kiosk_id: uuid.UUID, *, enabled: bool) -> None:
        """Sets or clears maintenance mode for a kiosk."""
        from sqlalchemy import update
        new_status = "MAINTENANCE" if enabled else "OFFLINE"
        await self._db.execute(
            update(Kiosk).where(Kiosk.id == kiosk_id).values(status=new_status)
        )
        await self._db.commit()
        logger.info("kiosk_maintenance_mode_set", kiosk_id=str(kiosk_id), enabled=enabled)

    async def deactivate_kiosk(self, kiosk_id: uuid.UUID) -> None:
        """Soft-disables a kiosk (no new jobs will be assigned)."""
        from sqlalchemy import update
        await self._db.execute(
            update(Kiosk).where(Kiosk.id == kiosk_id).values(is_active=False)
        )
        await self._db.commit()
        logger.info("kiosk_deactivated", kiosk_id=str(kiosk_id))

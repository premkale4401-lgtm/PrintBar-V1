"""
PrintBar Backend — Kiosk Repository

Data access layer for Kiosk, HeartbeatLog, and ApiKey records.
"""

from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.api_key import ApiKey
from app.models.heartbeat_log import HeartbeatLog
from app.models.kiosk import Kiosk

logger = get_logger(__name__)


class KioskRepository:
    """
    Repository for Kiosk, HeartbeatLog, and ApiKey operations.
    """

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_by_id(self, kiosk_id: uuid.UUID) -> Kiosk | None:
        result = await self._db.execute(
            select(Kiosk).where(Kiosk.id == kiosk_id, Kiosk.is_active.is_(True))
        )
        return result.scalar_one_or_none()

    async def get_by_api_key_hash(self, key_hash: str) -> Kiosk | None:
        """Looks up a kiosk by its API key hash for authentication."""
        result = await self._db.execute(
            select(Kiosk).where(
                Kiosk.api_key_hash == key_hash,
                Kiosk.is_active.is_(True),
            )
        )
        return result.scalar_one_or_none()

    async def get_all_active(self) -> list[Kiosk]:
        result = await self._db.execute(
            select(Kiosk).where(Kiosk.is_active.is_(True)).order_by(Kiosk.created_at)
        )
        return list(result.scalars().all())

    async def get_online_kiosks(self) -> list[Kiosk]:
        """Returns kiosks with status ONLINE or PRINTING."""
        result = await self._db.execute(
            select(Kiosk).where(
                Kiosk.is_active.is_(True),
                Kiosk.status.in_(["ONLINE", "PRINTING"]),
            )
        )
        return list(result.scalars().all())

    async def create(
        self,
        name: str,
        location: str,
        city: str,
        notes: str | None = None,
        latitude: float | None = None,
        longitude: float | None = None,
    ) -> tuple[Kiosk, str]:
        """
        Creates a new kiosk and generates its initial API key.

        Returns:
            Tuple of (Kiosk instance, raw API key string).
            The raw API key is shown ONCE and never stored.
        """
        raw_key = secrets.token_hex(32)  # 64 hex chars = 256-bit key
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()

        kiosk = Kiosk(
            name=name,
            location=location,
            city=city,
            api_key_hash=key_hash,
            notes=notes,
            latitude=latitude,
            longitude=longitude,
        )
        self._db.add(kiosk)
        await self._db.flush()

        # Also create an ApiKey record for tracking.
        api_key_record = ApiKey(
            kiosk_id=kiosk.id,
            key_hash=key_hash,
            key_prefix=raw_key[:8],
            is_active=True,
            description="Initial API key",
        )
        self._db.add(api_key_record)

        logger.info("kiosk_created", kiosk_id=str(kiosk.id), name=name)
        return kiosk, raw_key

    async def update_heartbeat(
        self,
        kiosk_id: uuid.UUID,
        *,
        status: str = "ONLINE",
        app_version: str | None = None,
        cpu_percent: float | None = None,
        ram_percent: float | None = None,
        disk_percent: float | None = None,
        temperature_c: float | None = None,
        printer_status: str | None = None,
    ) -> None:
        """Updates kiosk health metrics and last_heartbeat timestamp on heartbeat receipt."""
        now = datetime.now(tz=UTC).isoformat()
        values: dict = {
            "last_heartbeat": now,
            "status": status,
        }
        if app_version is not None:
            values["app_version"] = app_version
        if cpu_percent is not None:
            values["cpu_percent"] = cpu_percent
        if ram_percent is not None:
            values["ram_percent"] = ram_percent
        if disk_percent is not None:
            values["disk_percent"] = disk_percent
        if temperature_c is not None:
            values["temperature_c"] = temperature_c

        await self._db.execute(update(Kiosk).where(Kiosk.id == kiosk_id).values(**values))

    async def set_ws_connected(self, kiosk_id: uuid.UUID, connected: bool) -> None:
        """Updates the ws_connected flag when a WebSocket is opened or closed."""
        await self._db.execute(
            update(Kiosk)
            .where(Kiosk.id == kiosk_id)
            .values(ws_connected=connected, status="ONLINE" if connected else "OFFLINE")
        )

    async def log_heartbeat(
        self,
        kiosk_id: uuid.UUID,
        data: dict,
    ) -> HeartbeatLog:
        """Appends a HeartbeatLog entry."""
        import json

        extra = {
            k: v
            for k, v in data.items()
            if k
            not in (
                "cpu_percent",
                "ram_percent",
                "disk_percent",
                "temperature_c",
                "printer_status",
                "app_version",
                "network_latency_ms",
            )
        }

        log = HeartbeatLog(
            kiosk_id=kiosk_id,
            app_version=data.get("appVersion"),
            cpu_percent=data.get("cpuPercent"),
            ram_percent=data.get("ramPercent"),
            disk_percent=data.get("diskPercent"),
            temperature_c=data.get("temperatureC"),
            printer_status=data.get("printerStatus"),
            network_latency_ms=data.get("networkLatencyMs"),
            extra=json.dumps(extra) if extra else None,
        )
        self._db.add(log)
        return log

    async def rotate_api_key(self, kiosk_id: uuid.UUID) -> str:
        """
        Rotates the API key for a kiosk.

        Revokes the old key and creates a new one.
        Returns the new raw API key (shown once).
        """
        # Revoke existing active keys.
        from app.models.api_key import ApiKey as ApiKeyModel

        now = datetime.now(tz=UTC).isoformat()

        result = await self._db.execute(
            select(ApiKeyModel).where(
                ApiKeyModel.kiosk_id == kiosk_id,
                ApiKeyModel.is_active.is_(True),
            )
        )
        for old_key in result.scalars().all():
            old_key.is_active = False
            old_key.revoked_at = now
            old_key.revoke_reason = "ROTATED"

        # Generate new key.
        raw_key = secrets.token_hex(32)
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()

        new_api_key = ApiKeyModel(
            kiosk_id=kiosk_id,
            key_hash=key_hash,
            key_prefix=raw_key[:8],
            is_active=True,
            description="Rotated API key",
        )
        self._db.add(new_api_key)

        # Update Kiosk record.
        await self._db.execute(
            update(Kiosk).where(Kiosk.id == kiosk_id).values(api_key_hash=key_hash)
        )

        logger.info("kiosk_api_key_rotated", kiosk_id=str(kiosk_id))
        return raw_key

    @staticmethod
    def hash_api_key(raw_key: str) -> str:
        return hashlib.sha256(raw_key.encode()).hexdigest()

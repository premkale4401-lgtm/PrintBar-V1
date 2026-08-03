"""
PrintBar Backend — Kiosk HTTP Management Endpoints

POST /api/v1/kiosks/register       — Admin: provision a new kiosk (returns API key once)
POST /api/v1/kiosks/auth           — Kiosk: exchange API key for JWT
POST /api/v1/kiosks/heartbeat      — Kiosk: HTTP fallback heartbeat
GET  /api/v1/kiosks/{kiosk_id}     — Admin: kiosk detail + health metrics
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.security import jwt_handler
from app.database.session import get_db
from app.dependencies import get_current_admin
from app.models.user import User
from app.repositories.kiosk_repository import KioskRepository

logger = get_logger(__name__)
router = APIRouter(prefix="/kiosks", tags=["Kiosk Management"])
settings = get_settings()

class KioskRegisterRequest(BaseModel):
    """Request body for provisioning a new kiosk."""
    name: str = Field(..., min_length=1, max_length=255)
    location: str = Field(default="", max_length=512)
    city: str = Field(default="", max_length=100)
    notes: str | None = Field(default=None)
    latitude: float | None = Field(default=None)
    longitude: float | None = Field(default=None)

class KioskAuthRequest(BaseModel):
    """Request body for kiosk API key authentication."""
    kiosk_id: str = Field(...)
    api_key: str = Field(..., min_length=16)

class KioskHeartbeatRequest(BaseModel):
    """HTTP fallback heartbeat payload from kiosk agent."""
    kiosk_id: str = Field(...)
    printing: bool = Field(default=False)
    app_version: str | None = Field(default=None)
    cpu_percent: float | None = Field(default=None)
    ram_percent: float | None = Field(default=None)
    disk_percent: float | None = Field(default=None)
    temperature_c: float | None = Field(default=None)
    printer_status: str | None = Field(default=None)

@router.post("/register", status_code=status.HTTP_201_CREATED, summary="Admin: Provision a new kiosk")
async def register_kiosk(body: KioskRegisterRequest, current_user: User = Depends(get_current_admin), db: AsyncSession = Depends(get_db)) -> JSONResponse:
    """Creates a new kiosk and returns a one-time API key."""
    repo = KioskRepository(db)
    kiosk, raw_key = await repo.create(name=body.name, location=body.location, city=body.city, notes=body.notes, latitude=body.latitude, longitude=body.longitude)
    await db.commit()
    await db.refresh(kiosk)
    logger.info("kiosk_registered", kiosk_id=str(kiosk.id), name=body.name, admin_id=str(current_user.id))
    return JSONResponse(status_code=status.HTTP_201_CREATED, content={"success": True, "data": {"kioskId": str(kiosk.id), "name": kiosk.name, "location": kiosk.location, "city": kiosk.city, "apiKey": raw_key, "warning": "This API key will NOT be shown again. Configure it in kiosk.yaml immediately.", "createdAt": str(kiosk.created_at) if kiosk.created_at else None}})

@router.post("/auth", status_code=status.HTTP_200_OK, summary="Kiosk: Exchange API key for JWT")
async def authenticate_kiosk(body: KioskAuthRequest, db: AsyncSession = Depends(get_db)) -> JSONResponse:
    """Authenticates a kiosk via API key and returns a JWT."""
    try:
        kiosk_uuid = uuid.UUID(body.kiosk_id)
    except ValueError:
        return JSONResponse(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, content={"success": False, "error": {"code": "KSK_001", "message": "Invalid kiosk ID format."}})
    repo = KioskRepository(db)
    key_hash = KioskRepository.hash_api_key(body.api_key)
    kiosk = await repo.get_by_api_key_hash(key_hash)
    if kiosk is None or kiosk.id != kiosk_uuid:
        logger.warning("kiosk_auth_failed", kiosk_id=body.kiosk_id)
        return JSONResponse(status_code=status.HTTP_401_UNAUTHORIZED, content={"success": False, "error": {"code": "KSK_002", "message": "Invalid kiosk credentials."}})
    token = jwt_handler.create_access_token(subject=str(kiosk.id), role="KIOSK", extra_claims={"name": kiosk.name})
    logger.info("kiosk_authenticated_http", kiosk_id=str(kiosk.id), name=kiosk.name)
    return JSONResponse(status_code=status.HTTP_200_OK, content={"success": True, "data": {"accessToken": token, "kioskId": str(kiosk.id), "name": kiosk.name, "tokenType": "bearer"}})

@router.post("/heartbeat", status_code=status.HTTP_200_OK, summary="Kiosk: HTTP fallback heartbeat")
async def kiosk_heartbeat_http(body: KioskHeartbeatRequest, db: AsyncSession = Depends(get_db)) -> JSONResponse:
    """HTTP fallback heartbeat — updates kiosk status and metrics."""
    try:
        kiosk_uuid = uuid.UUID(body.kiosk_id)
    except ValueError:
        return JSONResponse(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, content={"success": False, "error": {"code": "KSK_001", "message": "Invalid kiosk ID format."}})
    repo = KioskRepository(db)
    kiosk = await repo.get_by_id(kiosk_uuid)
    if not kiosk:
        return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"success": False, "error": {"code": "KSK_003", "message": "Kiosk not found."}})
    await repo.update_heartbeat(kiosk_uuid, status="PRINTING" if body.printing else "ONLINE", app_version=body.app_version, cpu_percent=body.cpu_percent, ram_percent=body.ram_percent, disk_percent=body.disk_percent, temperature_c=body.temperature_c, printer_status=body.printer_status)
    await repo.log_heartbeat(kiosk_uuid, body.model_dump())
    await db.commit()
    return JSONResponse(status_code=status.HTTP_200_OK, content={"success": True, "data": {"kioskId": body.kiosk_id, "serverTime": datetime.now(tz=UTC).isoformat()}})

@router.get("/{kiosk_id}", status_code=status.HTTP_200_OK, summary="Admin: Get kiosk detail")
async def get_kiosk_detail(kiosk_id: uuid.UUID, current_user: User = Depends(get_current_admin), db: AsyncSession = Depends(get_db)) -> JSONResponse:
    """Returns detailed kiosk information including health metrics."""
    repo = KioskRepository(db)
    kiosk = await repo.get_by_id(kiosk_id)
    if not kiosk:
        return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"success": False, "error": {"code": "KSK_003", "message": "Kiosk not found."}})
    return JSONResponse(status_code=status.HTTP_200_OK, content={"success": True, "data": {"kioskId": str(kiosk.id), "name": kiosk.name, "location": kiosk.location, "city": kiosk.city, "status": kiosk.status, "isActive": kiosk.is_active, "wsConnected": kiosk.ws_connected, "lastHeartbeat": kiosk.last_heartbeat, "appVersion": kiosk.app_version, "cpuPercent": kiosk.cpu_percent, "ramPercent": kiosk.ram_percent, "diskPercent": kiosk.disk_percent, "temperatureC": kiosk.temperature_c, "latitude": kiosk.latitude, "longitude": kiosk.longitude, "notes": kiosk.notes, "createdAt": str(kiosk.created_at) if kiosk.created_at else None}})

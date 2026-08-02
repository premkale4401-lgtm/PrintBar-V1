"""
PrintBar Backend — Printer Management Endpoints

GET   /api/v1/printers             — Admin: list all printers
GET   /api/v1/printers/{id}        — Admin: printer detail
PATCH /api/v1/printers/{id}        — Admin: update printer config/status
POST  /api/v1/printers/test-print  — Admin: trigger a test print job

Printer status is primarily updated by the kiosk agent via WebSocket heartbeat.
These endpoints expose printer data to the admin dashboard.

All endpoints require admin authentication.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.database.session import get_db
from app.dependencies import get_current_admin, require_super_admin
from app.models.printer import Printer
from app.models.user import User

logger = get_logger(__name__)
router = APIRouter(prefix="/printers", tags=["Printer Management"])


# ─── Request Schemas ──────────────────────────────────────────────────────────

class PrinterUpdateRequest(BaseModel):
    """Request body for updating a printer's configuration."""

    is_default: bool | None = Field(default=None, description="Set as primary printer for the kiosk.")
    is_color: bool | None = Field(default=None, description="Color printing support override.")
    is_duplex: bool | None = Field(default=None, description="Duplex printing support override.")


# ─── List Printers ────────────────────────────────────────────────────────────

@router.get(
    "",
    status_code=status.HTTP_200_OK,
    summary="Admin: List all printers",
    description="Returns all registered printers and their current status. Requires admin authentication.",
)
async def list_printers(
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    """Returns all printer records from the database."""
    result = await db.execute(
        select(Printer).order_by(Printer.created_at)
    )
    printers = result.scalars().all()

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "success": True,
            "data": {
                "printers": [
                    {
                        "printerId": str(p.id),
                        "kioskId": str(p.kiosk_id) if p.kiosk_id else None,
                        "cupsName": p.cups_name,
                        "manufacturer": p.manufacturer,
                        "model": p.model,
                        "status": p.status,
                        "isDefault": p.is_default,
                        "isColor": p.is_color,
                        "isDuplex": p.is_duplex,
                        "paperLevel": p.paper_level,
                        "tonerLevel": p.toner_level,
                        "jobsPrinted": p.jobs_printed,
                        "lastError": p.last_error,
                        "createdAt": str(p.created_at) if p.created_at else None,
                    }
                    for p in printers
                ],
                "total": len(printers),
            },
        },
    )


# ─── Get Printer Detail ────────────────────────────────────────────────────────

@router.get(
    "/{printer_id}",
    status_code=status.HTTP_200_OK,
    summary="Admin: Get printer detail",
    description="Returns a single printer's detail and current status. Requires admin authentication.",
)
async def get_printer(
    printer_id: uuid.UUID,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    """Returns a single printer record."""
    result = await db.execute(
        select(Printer).where(Printer.id == printer_id)
    )
    printer = result.scalar_one_or_none()

    if not printer:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={
                "success": False,
                "error": {"code": "PRN_001", "message": "Printer not found."},
            },
        )

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "success": True,
            "data": {
                "printerId": str(printer.id),
                "kioskId": str(printer.kiosk_id) if printer.kiosk_id else None,
                "cupsName": printer.cups_name,
                "manufacturer": printer.manufacturer,
                "model": printer.model,
                "status": printer.status,
                "isDefault": printer.is_default,
                "isColor": printer.is_color,
                "isDuplex": printer.is_duplex,
                "paperLevel": printer.paper_level,
                "tonerLevel": printer.toner_level,
                "jobsPrinted": printer.jobs_printed,
                "lastError": printer.last_error,
                "createdAt": str(printer.created_at) if printer.created_at else None,
            },
        },
    )


# ─── Update Printer ────────────────────────────────────────────────────────────

@router.patch(
    "/{printer_id}",
    status_code=status.HTTP_200_OK,
    summary="Admin: Update printer configuration",
    description="Updates a printer's admin-configurable fields. Kiosk-reported status is not overridable here. Requires super admin authentication.",
)
async def update_printer(
    printer_id: uuid.UUID,
    body: PrinterUpdateRequest,
    current_user: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    """Updates admin-configurable printer fields."""
    result = await db.execute(
        select(Printer).where(Printer.id == printer_id)
    )
    printer = result.scalar_one_or_none()

    if not printer:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={
                "success": False,
                "error": {"code": "PRN_001", "message": "Printer not found."},
            },
        )

    if body.is_default is not None:
        printer.is_default = body.is_default
    if body.is_color is not None:
        printer.is_color = body.is_color
    if body.is_duplex is not None:
        printer.is_duplex = body.is_duplex

    await db.commit()
    await db.refresh(printer)

    logger.info(
        "printer_updated_by_admin",
        printer_id=str(printer_id),
        admin_id=str(current_user.id),
    )

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "success": True,
            "data": {
                "printerId": str(printer.id),
                "cupsName": printer.cups_name,
                "model": printer.model,
                "isDefault": printer.is_default,
                "isColor": printer.is_color,
                "isDuplex": printer.is_duplex,
            },
        },
    )


# ─── Test Print ────────────────────────────────────────────────────────────────

@router.post(
    "/test-print",
    status_code=status.HTTP_200_OK,
    summary="Admin: Trigger a test print on a kiosk",
    description=(
        "Sends a TEST_PRINT command to the specified kiosk via WebSocket. "
        "The kiosk prints a configuration/diagnostic page. "
        "Requires super admin authentication."
    ),
)
async def trigger_test_print(
    kiosk_id: uuid.UUID,
    current_user: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    """
    Sends a TEST_PRINT command to the kiosk via WebSocket.

    The kiosk must be ONLINE and connected to receive the command.
    """
    from app.websocket.manager import ws_manager
    from app.repositories.kiosk_repository import KioskRepository

    repo = KioskRepository(db)
    kiosk = await repo.get_by_id(kiosk_id)

    if not kiosk:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={
                "success": False,
                "error": {"code": "KSK_003", "message": "Kiosk not found."},
            },
        )

    if not kiosk.ws_connected:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={
                "success": False,
                "error": {
                    "code": "KSK_004",
                    "message": f"Kiosk '{kiosk.name}' is not currently connected.",
                },
            },
        )

    # Send TEST_PRINT command over WebSocket.
    await ws_manager.send_to_kiosk(
        str(kiosk_id),
        "TEST_PRINT",
        {
            "requestedBy": str(current_user.id),
            "requestedAt": datetime.now(tz=UTC).isoformat(),
        },
    )

    logger.info(
        "test_print_triggered",
        kiosk_id=str(kiosk_id),
        kiosk_name=kiosk.name,
        admin_id=str(current_user.id),
    )

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "success": True,
            "data": {
                "kioskId": str(kiosk_id),
                "message": f"TEST_PRINT command sent to {kiosk.name}.",
            },
        },
    )

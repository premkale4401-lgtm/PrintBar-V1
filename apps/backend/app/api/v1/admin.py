"""
PrintBar Backend — Admin Dashboard & Management Endpoints

GET  /api/v1/admin/dashboard          — Dashboard stats
GET  /api/v1/admin/jobs               — List print jobs (paginated)
GET  /api/v1/admin/kiosks             — List all kiosks
POST /api/v1/admin/kiosks             — Register a new kiosk
GET  /api/v1/admin/kiosks/{id}        — Kiosk details
POST /api/v1/admin/kiosks/{id}/rotate-key — Rotate kiosk API key
GET  /api/v1/admin/pricing            — Get all pricing rules
POST /api/v1/admin/pricing            — Create new pricing rule (deactivates old)
GET  /api/v1/admin/audit-logs         — View audit log
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.database.session import get_db
from app.dependencies import get_current_admin, require_super_admin
from app.models.audit_log import AuditLog
from app.models.kiosk import Kiosk
from app.models.payment import Payment
from app.models.print_job import PrintJob
from app.models.pricing_rule import PricingRule
from app.models.user import User
from app.repositories.kiosk_repository import KioskRepository
from app.websocket.manager import ws_manager

logger = get_logger(__name__)
router = APIRouter(prefix="/admin", tags=["Admin"])


@router.get("/dashboard", summary="Admin dashboard statistics")
async def get_dashboard(
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Returns aggregated platform statistics for the admin dashboard.

    Includes:
        - Today's job and revenue counts
        - Total lifetime stats
        - Active kiosk count
        - Recent jobs
    """
    today = datetime.now(tz=UTC).replace(hour=0, minute=0, second=0, microsecond=0)

    # Today's completed jobs.
    today_jobs_result = await db.execute(
        select(func.count(PrintJob.id)).where(
            PrintJob.status == "COMPLETED",
            PrintJob.completed_at >= today.isoformat(),
        )
    )
    today_jobs = today_jobs_result.scalar() or 0

    # Today's revenue.
    today_revenue_result = await db.execute(
        select(func.coalesce(func.sum(Payment.amount_inr), 0)).where(
            Payment.status == "SUCCESS",
            Payment.paid_at >= today.isoformat(),
        )
    )
    today_revenue = float(today_revenue_result.scalar() or 0)

    # Total completed jobs.
    total_jobs_result = await db.execute(
        select(func.count(PrintJob.id)).where(PrintJob.status == "COMPLETED")
    )
    total_jobs = total_jobs_result.scalar() or 0

    # Active kiosks.
    active_kiosks_result = await db.execute(
        select(func.count(Kiosk.id)).where(
            Kiosk.is_active.is_(True),
            Kiosk.status.in_(["ONLINE", "PRINTING"]),
        )
    )
    active_kiosks = active_kiosks_result.scalar() or 0

    # Jobs in queue.
    queued_result = await db.execute(
        select(func.count(PrintJob.id)).where(PrintJob.status == "QUEUED")
    )
    queued_jobs = queued_result.scalar() or 0

    # Recent 10 jobs.
    recent_result = await db.execute(
        select(PrintJob).order_by(PrintJob.created_at.desc()).limit(10)
    )
    recent_jobs = [
        {
            "jobId": str(j.id),
            "status": j.status,
            "colorMode": j.color_mode,
            "totalInr": str(j.total_inr),
            "createdAt": j.created_at.isoformat() if j.created_at else None,
        }
        for j in recent_result.scalars().all()
    ]

    return {
        "success": True,
        "data": {
            "today": {
                "jobsCompleted": today_jobs,
                "revenueInr": round(today_revenue, 2),
            },
            "total": {
                "jobsCompleted": total_jobs,
            },
            "activeKiosks": active_kiosks,
            "connectedKiosks": len(ws_manager.connected_kiosk_ids()),
            "queuedJobs": queued_jobs,
            "recentJobs": recent_jobs,
        },
    }


@router.get("/jobs", summary="List print jobs")
async def list_jobs(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status: str | None = Query(default=None),
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Returns paginated list of print jobs."""
    query = select(PrintJob)
    if status:
        query = query.where(PrintJob.status == status.upper())

    query = query.order_by(PrintJob.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(query)
    jobs = result.scalars().all()

    return {
        "success": True,
        "data": {
            "jobs": [
                {
                    "jobId": str(j.id),
                    "sessionId": j.session_id[:8] + "...",
                    "status": j.status,
                    "colorMode": j.color_mode,
                    "paperSize": j.paper_size,
                    "copies": j.copies,
                    "pagesSelected": j.pages_selected,
                    "totalInr": str(j.total_inr),
                    "kioskId": str(j.kiosk_id) if j.kiosk_id else None,
                    "createdAt": j.created_at.isoformat() if j.created_at else None,
                    "completedAt": j.completed_at,
                }
                for j in jobs
            ],
            "page": page,
            "pageSize": page_size,
        },
    }


@router.get("/kiosks", summary="List all kiosks")
async def list_kiosks(
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Returns all registered kiosks with live connection status."""
    repo = KioskRepository(db)
    kiosks = await repo.get_all_active()

    return {
        "success": True,
        "data": [
            {
                "kioskId": str(k.id),
                "name": k.name,
                "location": k.location,
                "city": k.city,
                "status": k.status,
                "wsConnected": ws_manager.is_connected(str(k.id)),
                "appVersion": k.app_version,
                "cpuPercent": k.cpu_percent,
                "ramPercent": k.ram_percent,
                "diskPercent": k.disk_percent,
                "temperatureC": k.temperature_c,
                "lastHeartbeat": k.last_heartbeat,
            }
            for k in kiosks
        ],
    }


@router.post("/kiosks", summary="Register a new kiosk", status_code=201)
async def create_kiosk(
    request,
    current_user: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Registers a new kiosk and returns the one-time API key.

    The API key is shown ONCE. Store it immediately.
    """
    body = await request.json()
    repo = KioskRepository(db)

    kiosk, raw_key = await repo.create(
        name=body["name"],
        location=body["location"],
        city=body.get("city", ""),
        notes=body.get("notes"),
        latitude=body.get("latitude"),
        longitude=body.get("longitude"),
    )

    logger.info("kiosk_registered_via_admin", kiosk_id=str(kiosk.id), name=kiosk.name)

    return {
        "success": True,
        "data": {
            "kioskId": str(kiosk.id),
            "name": kiosk.name,
            "apiKey": raw_key,
            "warning": "This API key is shown ONCE. Copy it now and store it securely.",
        },
    }


@router.post("/kiosks/{kiosk_id}/rotate-key", summary="Rotate kiosk API key")
async def rotate_kiosk_key(
    kiosk_id: uuid.UUID,
    current_user: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Rotates the API key for a kiosk. Old key is immediately revoked."""
    repo = KioskRepository(db)
    raw_key = await repo.rotate_api_key(kiosk_id)

    return {
        "success": True,
        "data": {
            "kioskId": str(kiosk_id),
            "apiKey": raw_key,
            "warning": "This API key is shown ONCE. Copy it now.",
        },
    }


@router.get("/pricing", summary="List pricing rules")
async def list_pricing(
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Returns all pricing rules in reverse chronological order."""
    result = await db.execute(
        select(PricingRule).order_by(PricingRule.created_at.desc())
    )
    rules = result.scalars().all()

    return {
        "success": True,
        "data": [
            {
                "id": str(r.id),
                "name": r.name,
                "bwPriceInr": str(r.bw_price_inr),
                "colorPriceInr": str(r.color_price_inr),
                "gstPercent": str(r.gst_percent),
                "isActive": r.is_active,
                "validFrom": r.valid_from,
                "notes": r.notes,
            }
            for r in rules
        ],
    }


@router.post("/pricing", summary="Create new pricing rule", status_code=201)
async def create_pricing_rule(
    request,
    current_user: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Creates a new pricing rule and deactivates all existing active rules.

    Only one pricing rule may be active at a time.
    """
    from decimal import Decimal
    body = await request.json()

    # Deactivate existing active rules.
    from sqlalchemy import update
    await db.execute(
        update(PricingRule)
        .where(PricingRule.is_active.is_(True))
        .values(is_active=False, valid_until=datetime.now(tz=UTC).isoformat())
    )

    rule = PricingRule(
        name=body["name"],
        bw_price_inr=Decimal(str(body["bwPriceInr"])),
        color_price_inr=Decimal(str(body["colorPriceInr"])),
        a3_multiplier=Decimal(str(body.get("a3Multiplier", "1.75"))),
        legal_multiplier=Decimal(str(body.get("legalMultiplier", "1.25"))),
        duplex_discount=Decimal(str(body.get("duplexDiscount", "0.00"))),
        gst_percent=Decimal(str(body.get("gstPercent", "18.00"))),
        is_active=True,
        valid_from=datetime.now(tz=UTC).isoformat(),
        notes=body.get("notes"),
    )
    db.add(rule)
    await db.flush()

    logger.info("pricing_rule_created", rule_id=str(rule.id), name=rule.name)

    return {
        "success": True,
        "data": {"id": str(rule.id), "name": rule.name, "active": True},
    }


@router.get("/audit-logs", summary="View audit log")
async def get_audit_logs(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    action: str | None = Query(default=None),
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Returns paginated audit log entries."""
    query = select(AuditLog)
    if action:
        query = query.where(AuditLog.action.ilike(f"%{action}%"))

    query = query.order_by(AuditLog.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(query)
    logs = result.scalars().all()

    return {
        "success": True,
        "data": [
            {
                "id": str(log.id),
                "actorType": log.actor_type,
                "action": log.action,
                "entityType": log.entity_type,
                "entityId": log.entity_id,
                "result": log.result,
                "ipAddress": log.ip_address,
                "createdAt": log.created_at.isoformat() if log.created_at else None,
            }
            for log in logs
        ],
        "page": page,
        "pageSize": page_size,
    }

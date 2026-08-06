"""
PrintBar Backend — Admin Dashboard & Management Endpoints

GET  /api/v1/admin/dashboard              — Dashboard stats
GET  /api/v1/admin/jobs                   — List print jobs (paginated, filterable)
GET  /api/v1/admin/kiosks                 — List all kiosks
POST /api/v1/admin/kiosks                 — Register a new kiosk
GET  /api/v1/admin/kiosks/{id}            — Single kiosk detail + recent heartbeats
POST /api/v1/admin/kiosks/{id}/rotate-key — Rotate kiosk API key
GET  /api/v1/admin/pricing                — Get all pricing rules
POST /api/v1/admin/pricing                — Create new pricing rule (deactivates old)
GET  /api/v1/admin/audit-logs             — View audit log
GET  /api/v1/admin/users                  — List platform users (admin only)
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.database.session import get_db
from app.dependencies import get_current_admin, require_super_admin
from app.models.audit_log import AuditLog
from app.models.heartbeat_log import HeartbeatLog
from app.models.kiosk import Kiosk
from app.models.payment import Payment
from app.models.pricing_rule import PricingRule
from app.models.print_job import PrintJob
from app.models.user import User
from app.repositories.kiosk_repository import KioskRepository
from app.websocket.manager import ws_manager

logger = get_logger(__name__)
router = APIRouter(prefix="/admin", tags=["Admin"])


# ─── Request Schemas ──────────────────────────────────────────────────────────


class CreateKioskRequest(BaseModel):
    """Request body for registering a new kiosk."""

    name: str = Field(..., min_length=1, max_length=100, description="Human-readable kiosk name.")
    location: str = Field(
        ..., min_length=1, max_length=200, description="Physical location description."
    )
    city: str = Field(default="", max_length=100, description="City where the kiosk is deployed.")
    notes: str | None = Field(default=None, max_length=500, description="Optional operator notes.")
    latitude: float | None = Field(default=None, description="GPS latitude.")
    longitude: float | None = Field(default=None, description="GPS longitude.")


class CreatePricingRuleRequest(BaseModel):
    """Request body for creating a new pricing rule."""

    name: str = Field(
        ..., min_length=1, max_length=100, description="Rule name (e.g. 'Standard 2026')."
    )
    bwPriceInr: str = Field(
        ..., description="Black & white price per page in INR (Decimal string)."
    )
    colorPriceInr: str = Field(..., description="Color price per page in INR (Decimal string).")
    a3Multiplier: str = Field(default="1.75", description="A3 size price multiplier.")
    legalMultiplier: str = Field(default="1.25", description="Legal size price multiplier.")
    duplexDiscount: str = Field(default="0.00", description="Duplex discount per page in INR.")
    gstPercent: str = Field(default="18.00", description="GST percentage to apply.")
    notes: str | None = Field(default=None, max_length=500, description="Optional rule notes.")


# ─── Dashboard ────────────────────────────────────────────────────────────────


@router.get("/dashboard", summary="Admin dashboard statistics")
async def get_dashboard(
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Returns aggregated platform statistics for the admin dashboard.

    Includes today's job and revenue counts, total lifetime stats,
    active kiosk count, queued jobs, and the 10 most recent jobs.
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

    # Active kiosks (ONLINE or PRINTING).
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


# ─── Jobs ─────────────────────────────────────────────────────────────────────


@router.get("/jobs", summary="List print jobs")
async def list_jobs(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status: str | None = Query(default=None, description="Filter by job status."),
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Returns a paginated list of print jobs, optionally filtered by status."""
    query = select(PrintJob)
    if status:
        query = query.where(PrintJob.status == status.upper())

    query = query.order_by(PrintJob.created_at.desc())

    # Total count for pagination.
    count_query = select(func.count(PrintJob.id))
    if status:
        count_query = count_query.where(PrintJob.status == status.upper())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

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
            "total": total,
        },
    }


@router.get("/jobs/{job_id}/timeline", summary="Get job timeline")
async def get_job_timeline(
    job_id: uuid.UUID,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Returns the audit log timeline for a specific print job."""
    import json

    # Check if job exists
    job = await db.execute(select(PrintJob).where(PrintJob.id == job_id))
    if not job.scalar_one_or_none():
        from fastapi import HTTPException

        raise HTTPException(
            status_code=404, detail={"code": "JOB_001", "message": "Job not found."}
        )

    # Fetch audit logs related to this job
    result = await db.execute(
        select(AuditLog).where(AuditLog.print_job_id == job_id).order_by(AuditLog.created_at.asc())
    )
    logs = result.scalars().all()

    return {
        "success": True,
        "data": [
            {
                "id": str(log.id),
                "action": log.action,
                "result": log.result,
                "details": json.loads(log.details) if log.details else None,
                "createdAt": log.created_at.isoformat() if log.created_at else None,
            }
            for log in logs
        ],
    }


# ─── Kiosks ───────────────────────────────────────────────────────────────────


@router.get("/kiosks", summary="List all kiosks")
async def list_kiosks(
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Returns all registered kiosks with live connection status and health metrics."""
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


@router.get("/kiosks/{kiosk_id}", summary="Get kiosk detail")
async def get_kiosk_detail(
    kiosk_id: uuid.UUID,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Returns detailed information for a single kiosk including recent heartbeat history."""
    repo = KioskRepository(db)
    kiosk = await repo.get_by_id(kiosk_id)

    if not kiosk:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=404, detail={"code": "KIOSK_001", "message": "Kiosk not found."}
        )

    # Recent heartbeat logs (last 20).
    heartbeat_result = await db.execute(
        select(HeartbeatLog)
        .where(HeartbeatLog.kiosk_id == kiosk_id)
        .order_by(HeartbeatLog.created_at.desc())
        .limit(20)
    )
    heartbeats = [
        {
            "receivedAt": h.created_at.isoformat() if h.created_at else None,
            "cpuPercent": h.cpu_percent,
            "ramPercent": h.ram_percent,
            "diskPercent": h.disk_percent,
            "temperatureC": h.temperature_c,
            "printerStatus": h.printer_status,
        }
        for h in heartbeat_result.scalars().all()
    ]

    # Job counts for this kiosk.
    jobs_today_result = await db.execute(
        select(func.count(PrintJob.id)).where(
            PrintJob.kiosk_id == kiosk_id,
            PrintJob.status == "COMPLETED",
            PrintJob.completed_at
            >= datetime.now(tz=UTC).replace(hour=0, minute=0, second=0, microsecond=0).isoformat(),
        )
    )
    jobs_today = jobs_today_result.scalar() or 0

    jobs_total_result = await db.execute(
        select(func.count(PrintJob.id)).where(
            PrintJob.kiosk_id == kiosk_id,
            PrintJob.status == "COMPLETED",
        )
    )
    jobs_total = jobs_total_result.scalar() or 0

    return {
        "success": True,
        "data": {
            "kioskId": str(kiosk.id),
            "name": kiosk.name,
            "location": kiosk.location,
            "city": kiosk.city,
            "status": kiosk.status,
            "wsConnected": ws_manager.is_connected(str(kiosk.id)),
            "isActive": kiosk.is_active,
            "appVersion": kiosk.app_version,
            "cpuPercent": kiosk.cpu_percent,
            "ramPercent": kiosk.ram_percent,
            "diskPercent": kiosk.disk_percent,
            "temperatureC": kiosk.temperature_c,
            "lastHeartbeat": kiosk.last_heartbeat,
            "jobsCompletedToday": jobs_today,
            "jobsCompletedTotal": jobs_total,
            "recentHeartbeats": heartbeats,
        },
    }


@router.post("/kiosks", summary="Register a new kiosk", status_code=201)
async def create_kiosk(
    body: CreateKioskRequest,
    current_user: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Registers a new kiosk and returns the one-time API key.

    The API key is shown ONCE and never retrievable again.
    Store it immediately in the kiosk's configuration file.
    """
    repo = KioskRepository(db)

    kiosk, raw_key = await repo.create(
        name=body.name,
        location=body.location,
        city=body.city,
        notes=body.notes,
        latitude=body.latitude,
        longitude=body.longitude,
    )

    logger.info("kiosk_registered_via_admin", kiosk_id=str(kiosk.id), name=kiosk.name)
    await db.commit()

    return {
        "success": True,
        "data": {
            "kioskId": str(kiosk.id),
            "name": kiosk.name,
            "apiKey": raw_key,
            "warning": "This API key is shown ONCE. Copy it now and store it securely in kiosk.yaml.",
        },
    }


@router.post("/kiosks/{kiosk_id}/rotate-key", summary="Rotate kiosk API key")
async def rotate_kiosk_key(
    kiosk_id: uuid.UUID,
    current_user: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Rotates the API key for a kiosk. The old key is immediately revoked.

    The kiosk will disconnect on the next heartbeat timeout and must
    be reconfigured with the new key before reconnecting.
    """
    repo = KioskRepository(db)
    raw_key = await repo.rotate_api_key(kiosk_id)

    logger.info("kiosk_api_key_rotated", kiosk_id=str(kiosk_id))
    await db.commit()

    return {
        "success": True,
        "data": {
            "kioskId": str(kiosk_id),
            "apiKey": raw_key,
            "warning": "This API key is shown ONCE. Update kiosk.yaml immediately.",
        },
    }


# ─── Pricing ──────────────────────────────────────────────────────────────────


@router.get("/pricing", summary="List pricing rules")
async def list_pricing(
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Returns all pricing rules in reverse chronological order. Only one can be active."""
    result = await db.execute(select(PricingRule).order_by(PricingRule.created_at.desc()))
    rules = result.scalars().all()

    return {
        "success": True,
        "data": [
            {
                "id": str(r.id),
                "name": r.name,
                "bwPriceInr": str(r.bw_price_inr),
                "colorPriceInr": str(r.color_price_inr),
                "a3Multiplier": str(r.a3_multiplier),
                "legalMultiplier": str(r.legal_multiplier),
                "duplexDiscount": str(r.duplex_discount),
                "gstPercent": str(r.gst_percent),
                "isActive": r.is_active,
                "validFrom": r.valid_from,
                "validUntil": r.valid_until,
                "notes": r.notes,
            }
            for r in rules
        ],
    }


@router.post("/pricing", summary="Create new pricing rule", status_code=201)
async def create_pricing_rule(
    body: CreatePricingRuleRequest,
    current_user: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Creates a new pricing rule and deactivates all existing active rules.

    Only one pricing rule can be active at a time.
    The previous rule is archived with a valid_until timestamp.
    """
    # Deactivate existing active rules.
    await db.execute(
        update(PricingRule)
        .where(PricingRule.is_active.is_(True))
        .values(is_active=False, valid_until=datetime.now(tz=UTC).isoformat())
    )

    rule = PricingRule(
        name=body.name,
        bw_price_inr=Decimal(body.bwPriceInr),
        color_price_inr=Decimal(body.colorPriceInr),
        a3_multiplier=Decimal(body.a3Multiplier),
        legal_multiplier=Decimal(body.legalMultiplier),
        duplex_discount=Decimal(body.duplexDiscount),
        gst_percent=Decimal(body.gstPercent),
        is_active=True,
        valid_from=datetime.now(tz=UTC).isoformat(),
        notes=body.notes,
    )
    db.add(rule)
    await db.flush()
    await db.commit()

    logger.info("pricing_rule_created", rule_id=str(rule.id), name=rule.name)

    return {
        "success": True,
        "data": {
            "id": str(rule.id),
            "name": rule.name,
            "active": True,
        },
    }


# ─── Audit Logs ───────────────────────────────────────────────────────────────


@router.get("/audit-logs", summary="View audit log")
async def get_audit_logs(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    action: str | None = Query(default=None, description="Filter by action name (partial match)."),
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Returns a paginated audit log. Filterable by action name."""
    query = select(AuditLog)
    if action:
        query = query.where(AuditLog.action.ilike(f"%{action}%"))

    count_query = select(func.count(AuditLog.id))
    if action:
        count_query = count_query.where(AuditLog.action.ilike(f"%{action}%"))
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

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
        "total": total,
    }


# ─── Users ────────────────────────────────────────────────────────────────────


@router.get("/users", summary="List platform users")
async def list_users(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Returns a paginated list of admin platform users.

    Super admin only. Kiosk operators and end-users (guests) are not stored
    as User records — only admin accounts registered via seed_db.py appear here.
    """
    count_result = await db.execute(select(func.count(User.id)))
    total = count_result.scalar() or 0

    result = await db.execute(
        select(User)
        .order_by(User.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    users = result.scalars().all()

    return {
        "success": True,
        "data": {
            "users": [
                {
                    "id": str(u.id),
                    "name": u.name,
                    "email": u.email,
                    "role": u.role,
                    "isActive": u.is_active,
                    "lastLoginAt": u.last_login_at,
                    "createdAt": u.created_at.isoformat() if u.created_at else None,
                }
                for u in users
            ],
            "page": page,
            "pageSize": page_size,
            "total": total,
        },
    }

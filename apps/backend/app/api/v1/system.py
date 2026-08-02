"""
PrintBar Backend — System Status & Monitoring Endpoints

GET /api/v1/system/status   — Platform-wide health + component status

Returns aggregated status for:
    - Database connectivity
    - Redis connectivity
    - Supabase Storage connectivity
    - Active WebSocket connections
    - Queue depth (QUEUED print jobs)
    - Payment provider mode
    - Background workers (derived)

Used by the admin dashboard status panel and external monitoring tools.
Admin authentication required.
"""
from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.database.session import get_db
from app.dependencies import get_current_admin
from app.models.kiosk import Kiosk
from app.models.print_job import PrintJob
from app.models.user import User
from app.websocket.manager import ws_manager

logger = get_logger(__name__)
router = APIRouter(prefix="/system", tags=["System"])
settings = get_settings()


@router.get(
    "/status",
    status_code=status.HTTP_200_OK,
    summary="System-wide platform health and status",
    description=(
        "Returns the health and status of all platform components. "
        "Used by the admin dashboard and external monitoring. "
        "Requires admin authentication."
    ),
)
async def get_system_status(
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    """
    Aggregates the health status of all platform components.

    Returns component-level status plus aggregated counts for dashboard display.
    Does not raise exceptions on component failure — reports degraded status instead.
    """
    checks: dict[str, dict] = {}

    # ── Database ────────────────────────────────────────────────────────────────
    try:
        await db.execute(text("SELECT 1"))
        checks["database"] = {"status": "ok", "latency_ms": None}
    except Exception as exc:
        logger.error("system_status_db_fail", error=str(exc))
        checks["database"] = {"status": "error", "error": str(exc)}

    # ── Redis ────────────────────────────────────────────────────────────────────
    try:
        import redis.asyncio as aioredis
        r = await aioredis.from_url(settings.REDIS_URL, socket_connect_timeout=2)
        await r.ping()
        await r.aclose()
        checks["redis"] = {"status": "ok"}
    except Exception as exc:
        checks["redis"] = {"status": "error", "error": "Redis unavailable"}

    # ── Supabase Storage ────────────────────────────────────────────────────────
    try:
        from app.storage.service import storage_service
        exists = await storage_service.file_exists(
            settings.STORAGE_BUCKET_PRINT_FILES, "_health_check_probe"
        )
        # A False result is fine (file doesn't exist) — it means storage is reachable.
        checks["storage"] = {"status": "ok", "bucket": settings.STORAGE_BUCKET_PRINT_FILES}
    except Exception as exc:
        checks["storage"] = {"status": "error", "error": "Storage unavailable"}

    # ── Active WebSocket Connections ─────────────────────────────────────────────
    active_ws = len(ws_manager._connections)
    checks["websocket"] = {"status": "ok", "active_connections": active_ws}

    # ── Print Job Queue ──────────────────────────────────────────────────────────
    try:
        queue_result = await db.execute(
            select(func.count(PrintJob.id)).where(PrintJob.status == "QUEUED")
        )
        queue_depth = queue_result.scalar() or 0

        active_result = await db.execute(
            select(func.count(PrintJob.id)).where(
                PrintJob.status.in_(["ASSIGNED", "DOWNLOADING", "READY_TO_PRINT", "PRINTING"])
            )
        )
        active_jobs = active_result.scalar() or 0

        checks["queue"] = {
            "status": "ok",
            "queued": queue_depth,
            "active": active_jobs,
        }
    except Exception as exc:
        checks["queue"] = {"status": "error", "error": str(exc)}

    # ── Kiosks ────────────────────────────────────────────────────────────────────
    try:
        online_result = await db.execute(
            select(func.count(Kiosk.id)).where(
                Kiosk.is_active.is_(True),
                Kiosk.status.in_(["ONLINE", "PRINTING"]),
            )
        )
        online_kiosks = online_result.scalar() or 0

        total_result = await db.execute(
            select(func.count(Kiosk.id)).where(Kiosk.is_active.is_(True))
        )
        total_kiosks = total_result.scalar() or 0

        checks["kiosks"] = {
            "status": "ok",
            "online": online_kiosks,
            "total": total_kiosks,
        }
    except Exception as exc:
        checks["kiosks"] = {"status": "error", "error": str(exc)}

    # ── Overall Health ────────────────────────────────────────────────────────────
    critical_components = ["database"]
    is_healthy = all(
        checks.get(c, {}).get("status") == "ok"
        for c in critical_components
    )
    is_degraded = any(
        checks.get(c, {}).get("status") != "ok"
        for c in ["redis", "storage", "websocket"]
    )

    overall = "healthy" if is_healthy and not is_degraded else (
        "degraded" if is_healthy else "unhealthy"
    )

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "success": True,
            "data": {
                "overall": overall,
                "timestamp": datetime.now(tz=UTC).isoformat(),
                "environment": settings.ENVIRONMENT,
                "version": settings.APP_VERSION,
                "paymentProvider": settings.PAYMENT_PROVIDER,
                "isMockPayment": settings.is_mock_payment,
                "components": checks,
            },
        },
    )

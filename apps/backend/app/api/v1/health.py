"""
PrintBar Backend — Health Check API

Provides three standard health endpoints required for container orchestration
and production monitoring as specified in doc 12.

Endpoints:
    GET /health — Simple liveness check. No auth. No dependencies.
    GET /ready  — Readiness check. Verifies DB, Redis, and Storage are reachable.
    GET /live   — Container liveness probe (same as /health for now).
"""

import uuid

import redis.asyncio as aioredis
from fastapi import APIRouter, status
from fastapi.responses import JSONResponse

from app.core.config import get_settings
from app.core.logging import get_logger
from app.database.session import check_database_connectivity

logger = get_logger(__name__)
router = APIRouter(tags=["Health"])

_settings = get_settings()


@router.get(
    "/health",
    summary="Liveness check",
    description="Returns 200 immediately if the process is running. No dependency checks.",
    response_description="Application is alive",
)
async def health() -> dict:
    """
    Simple liveness check. Returns 200 if the application process is running.

    Used by Docker health checks and load balancers to determine
    whether the container is alive.

    Returns:
        JSON: {"status": "healthy"}
    """
    return {"status": "healthy"}


@router.get(
    "/live",
    summary="Container liveness probe",
    description="Kubernetes/Docker liveness probe endpoint.",
    response_description="Container is alive",
)
async def live() -> dict:
    """
    Container liveness probe. Identical to /health.

    Returns:
        JSON: {"status": "alive"}
    """
    return {"status": "alive"}


@router.get(
    "/ready",
    summary="Readiness probe",
    description=(
        "Checks all critical dependencies: PostgreSQL, Redis, and Supabase Storage. "
        "Returns 200 only if all dependencies are reachable. "
        "Returns 503 if any dependency is unavailable."
    ),
    response_description="System readiness status with per-component health",
)
async def ready() -> JSONResponse:
    """
    Readiness probe that verifies all external dependencies.

    Checks:
        - PostgreSQL database connectivity
        - Redis connectivity
        - Supabase Storage reachability

    Returns:
        200: All systems ready.
        503: One or more systems are unavailable.
    """
    checks: dict[str, bool] = {}
    request_id = str(uuid.uuid4())

    # ─── Database ──────────────────────────────────────────────────────────────
    try:
        checks["database"] = await check_database_connectivity()
    except Exception as exc:
        logger.error("readiness_db_check_failed", error=str(exc), request_id=request_id)
        checks["database"] = False

    # ─── Redis ─────────────────────────────────────────────────────────────────
    if _settings.REDIS_URL:
        try:
            redis_client = aioredis.from_url(
                _settings.REDIS_URL,
                socket_connect_timeout=2,
            )
            await redis_client.ping()
            await redis_client.aclose()
            checks["redis"] = True
        except Exception as exc:
            logger.error("readiness_redis_check_failed", error=str(exc), request_id=request_id)
            checks["redis"] = False
    else:
        checks["redis"] = True

    # ─── Supabase Storage ──────────────────────────────────────────────────────
    if _settings.SUPABASE_URL:
        try:
            import httpx
            async with httpx.AsyncClient(timeout=3.0) as client:
                resp = await client.get(
                    f"{_settings.SUPABASE_URL}/storage/v1/bucket",
                    headers={"Authorization": f"Bearer {_settings.SUPABASE_SERVICE_ROLE_KEY}"},
                )
                checks["storage"] = resp.status_code in (200, 400)  # 400 = auth error but reachable
        except Exception as exc:
            logger.error("readiness_storage_check_failed", error=str(exc), request_id=request_id)
            checks["storage"] = False
    else:
        checks["storage"] = True

    all_ready = all(checks.values())
    status_code = status.HTTP_200_OK if all_ready else status.HTTP_503_SERVICE_UNAVAILABLE

    body = {
        "status": "ready" if all_ready else "not_ready",
        "checks": checks,
        "requestId": request_id,
    }

    if not all_ready:
        logger.warning("readiness_check_failed", checks=checks, request_id=request_id)

    return JSONResponse(content=body, status_code=status_code)

"""
PrintBar Backend — FastAPI Application Factory

Creates and configures the FastAPI application with all middleware,
exception handlers, routers, lifespan events, and OpenAPI settings.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.v1.admin import router as admin_router
from app.api.v1.admin_auth import router as admin_auth_router
from app.api.v1.dev_payment import router as dev_payment_router

# ─── Router Imports ────────────────────────────────────────────────────────────
from app.api.v1.health import router as health_router
from app.api.v1.jobs import router as jobs_router
from app.api.v1.kiosk_ws import router as kiosk_ws_router
from app.api.v1.kiosks import router as kiosks_router
from app.api.v1.payment import router as payment_router
from app.api.v1.pricing import router as pricing_router
from app.api.v1.printers import router as printers_router
from app.api.v1.session import router as session_router
from app.api.v1.system import router as system_router
from app.api.v1.upload import router as upload_router
from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.database.session import engine
from app.exceptions.base import PrintBarError
from app.exceptions.handlers import (
    http_exception_handler,
    printbar_exception_handler,
    unhandled_exception_handler,
    validation_exception_handler,
)
from app.middleware.logging_middleware import LoggingMiddleware
from app.middleware.request_id import RequestIDMiddleware
from app.middleware.security_headers import SecurityHeadersMiddleware
from app.core.rate_limit import limiter
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

logger = get_logger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Application lifespan manager.

    Startup:
        - Configures structured logging.
        - Verifies database connectivity.
        - Starts all background workers.

    Shutdown:
        - Disposes the SQLAlchemy connection pool.
    """
    # ─── Startup ───────────────────────────────────────────────────────────────
    configure_logging()
    log = get_logger(__name__)

    log.info(
        "application_starting",
        name=settings.APP_NAME,
        version=settings.APP_VERSION,
        environment=settings.ENVIRONMENT,
    )

    # ─── Configuration Validation ─────────────────────────────────────────────
    try:
        settings.validate_all()
    except Exception as e:
        log.error("configuration_invalid", error=str(e))
        raise RuntimeError(f"Startup failed: Invalid configuration. {str(e)}") from e

    # ─── Database Validation ──────────────────────────────────────────────────
    from sqlalchemy import text

    from app import models  # noqa: F401
    from app.database.session import check_database_connectivity

    db_ok = await check_database_connectivity()
    if not db_ok:
        log.error("database_not_reachable_at_startup")
        raise RuntimeError("Startup failed: Database is not reachable.")
    log.info("database_connection_verified")

    # Verify migrations explicitly instead of automatic schema creation
    try:
        async with engine.begin() as conn:
            # Note: For fresh sqlite databases, checking the table will raise OperationalError
            result = await conn.execute(text("SELECT version_num FROM alembic_version"))
            if not result.scalar():
                raise RuntimeError("No alembic_version found.")
    except Exception as e:
        log.error("migrations_missing", error=str(e))
        raise RuntimeError("Startup failed: Database migrations are not applied. Run 'alembic upgrade head'.") from e
    log.info("database_migrations_verified")

    # ─── Redis Validation ─────────────────────────────────────────────────────
    if settings.REDIS_URL:
        import redis.asyncio as aioredis
        try:
            redis_client = aioredis.from_url(settings.REDIS_URL, socket_connect_timeout=2)  # type: ignore[no-untyped-call]
            await redis_client.ping()
            await redis_client.aclose()
            log.info("redis_connection_verified")
        except Exception as e:
            log.error("redis_not_reachable_at_startup", error=str(e))
            raise RuntimeError("Startup failed: Redis is not reachable.") from e
    else:
        log.info("redis_skipped_in_development")

    # Start background workers.
    from app.workers.background import start_all_workers, stop_all_workers
    await start_all_workers()

    log.info("application_ready", name=settings.APP_NAME)

    yield

    # ─── Shutdown ──────────────────────────────────────────────────────────────
    log.info("application_shutting_down")
    await stop_all_workers()
    await engine.dispose()
    log.info("application_stopped")


def create_application() -> FastAPI:
    """
    Creates the FastAPI application with all configuration applied.
    """
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description=(
            "PrintBar — Production-grade QR-based self-service printing platform. "
            "This API is the single backend authority for all business logic."
        ),
        openapi_url="/openapi.json" if not settings.is_production else None,
        docs_url="/docs" if not settings.is_production else None,
        redoc_url="/redoc" if not settings.is_production else None,
        lifespan=lifespan,
    )
    
    app.state.limiter = limiter

    # ─── Middleware (last registered = outermost) ──────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization", "X-Request-ID", "X-Client-Version"],
        expose_headers=["X-Request-ID"],
    )
    app.add_middleware(SlowAPIMiddleware)
    app.add_middleware(LoggingMiddleware)
    app.add_middleware(RequestIDMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)

    # ─── Exception Handlers ────────────────────────────────────────────────────
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_exception_handler(PrintBarError, printbar_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, validation_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, unhandled_exception_handler)

    # ─── Routers ───────────────────────────────────────────────────────────────
    # Health — at root level for load balancers (no /api/v1 prefix).
    app.include_router(health_router)

    # WebSocket — kiosk connections (no /api/v1 prefix; WS at /ws/kiosk/{id}).
    app.include_router(kiosk_ws_router)

    # Guest-facing endpoints.
    app.include_router(session_router, prefix=settings.API_V1_PREFIX)
    app.include_router(upload_router, prefix=settings.API_V1_PREFIX)
    app.include_router(pricing_router, prefix=settings.API_V1_PREFIX)
    app.include_router(payment_router, prefix=settings.API_V1_PREFIX)
    app.include_router(jobs_router, prefix=settings.API_V1_PREFIX)

    # Admin endpoints.
    app.include_router(admin_auth_router, prefix=settings.API_V1_PREFIX)
    app.include_router(admin_router, prefix=settings.API_V1_PREFIX)
    app.include_router(kiosks_router, prefix=settings.API_V1_PREFIX)
    app.include_router(printers_router, prefix=settings.API_V1_PREFIX)
    app.include_router(system_router, prefix=settings.API_V1_PREFIX)

    # Mock payment bypass — available in dev mode OR when PAYMENT_PROVIDER=mock.
    # Never active when a real payment provider is configured in production.
    if settings.ENVIRONMENT == "development" or settings.is_mock_payment:
        app.include_router(dev_payment_router, prefix=settings.API_V1_PREFIX)
        
    # ─── Metrics ───────────────────────────────────────────────────────────────
    if settings.ENABLE_METRICS:
        from prometheus_client import make_asgi_app
        metrics_app = make_asgi_app()
        app.mount("/metrics", metrics_app)

    # ─── Local Storage Fallback ────────────────────────────────────────────────
    if not settings.SUPABASE_URL:
        from fastapi.staticfiles import StaticFiles
        import os
        
        # Ensure the local storage directory exists
        os.makedirs("data/storage", exist_ok=True)
        app.mount("/local-storage", StaticFiles(directory="data/storage"), name="local_storage")

    return app


# Module-level application instance used by Uvicorn.
app = create_application()

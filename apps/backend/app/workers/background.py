"""
PrintBar Backend — Background Workers

Runs on application startup via FastAPI lifespan.

Workers:
    1. CleanupWorker  — Deletes expired uploads every 15 min
    2. HeartbeatMonitor — Marks kiosks OFFLINE if no heartbeat in 90s (every 30s)
    3. PaymentExpiryWorker — Expires timed-out payments every 5 min
    4. JobDispatchWorker — Dispatches QUEUED jobs every 30s (belt-and-suspenders)
"""
from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import structlog

from app.core.config import get_settings
from app.core.logging import get_logger
from app.database.session import AsyncSessionFactory

logger = get_logger(__name__)
settings = get_settings()


async def run_cleanup_worker() -> None:
    """
    Deletes expired uploaded files from Supabase Storage and nulls their DB records.

    Runs every CLEANUP_WORKER_INTERVAL_MINUTES minutes.
    """
    logger.info("cleanup_worker_started")

    while True:
        try:
            async with AsyncSessionFactory() as db:
                async with db.begin():
                    from app.repositories.uploaded_file_repository import UploadedFileRepository
                    from app.storage.service import storage_service

                    repo = UploadedFileRepository(db)
                    expired = await repo.get_expired_undeleted()

                    for file in expired:
                        if file.storage_path:
                            await storage_service.delete_file(
                                bucket=file.storage_bucket,
                                object_path=file.storage_path,
                            )
                        await repo.mark_deleted(file.id)

                    if expired:
                        logger.info("cleanup_files_deleted", count=len(expired))

        except Exception as exc:
            logger.exception("cleanup_worker_error", error=str(exc))

        await asyncio.sleep(settings.CLEANUP_WORKER_INTERVAL_MINUTES * 60)


async def run_heartbeat_monitor() -> None:
    """
    Marks kiosks as OFFLINE if they haven't sent a heartbeat within the threshold.

    Runs every 30 seconds.
    """
    logger.info("heartbeat_monitor_started")

    while True:
        try:
            async with AsyncSessionFactory() as db:
                async with db.begin():
                    from sqlalchemy import select, update
                    from app.models.kiosk import Kiosk
                    from app.websocket.manager import ws_manager

                    now = datetime.now(tz=UTC).isoformat()
                    threshold_seconds = settings.WS_KIOSK_OFFLINE_THRESHOLD_SECONDS

                    # Find kiosks that are supposedly ONLINE but have stale heartbeats.
                    result = await db.execute(
                        select(Kiosk).where(
                            Kiosk.is_active.is_(True),
                            Kiosk.status.in_(["ONLINE", "PRINTING"]),
                            Kiosk.last_heartbeat.isnot(None),
                        )
                    )
                    kiosks = result.scalars().all()

                    for kiosk in kiosks:
                        if not kiosk.last_heartbeat:
                            continue

                        last_hb = datetime.fromisoformat(kiosk.last_heartbeat)
                        if last_hb.tzinfo is None:
                            last_hb = last_hb.replace(tzinfo=UTC)

                        elapsed = (datetime.now(tz=UTC) - last_hb).total_seconds()

                        if elapsed > threshold_seconds:
                            await db.execute(
                                update(Kiosk)
                                .where(Kiosk.id == kiosk.id)
                                .values(status="OFFLINE", ws_connected=False)
                            )
                            logger.warning(
                                "kiosk_marked_offline_heartbeat_timeout",
                                kiosk_id=str(kiosk.id),
                                elapsed_seconds=elapsed,
                            )

        except Exception as exc:
            logger.exception("heartbeat_monitor_error", error=str(exc))

        await asyncio.sleep(settings.WS_HEARTBEAT_INTERVAL_SECONDS)


async def run_payment_expiry_worker() -> None:
    """
    Marks PENDING payments as EXPIRED if they pass their expires_at timestamp.
    Also transitions associated print jobs to PAYMENT_FAILED.

    Runs every 5 minutes.
    """
    logger.info("payment_expiry_worker_started")

    while True:
        try:
            async with AsyncSessionFactory() as db:
                async with db.begin():
                    from sqlalchemy import select, update
                    from app.models.payment import Payment
                    from app.repositories.print_job_repository import PrintJobRepository

                    now = datetime.now(tz=UTC).isoformat()

                    result = await db.execute(
                        select(Payment).where(
                            Payment.status.in_(["CREATED", "PENDING"]),
                            Payment.expires_at.isnot(None),
                            Payment.expires_at <= now,
                        )
                    )
                    expired_payments = result.scalars().all()

                    if expired_payments:
                        job_repo = PrintJobRepository(db)
                        for payment in expired_payments:
                            await db.execute(
                                update(Payment)
                                .where(Payment.id == payment.id)
                                .values(status="EXPIRED")
                            )
                            try:
                                await job_repo.transition(payment.print_job_id, "PAYMENT_FAILED")
                            except Exception:
                                pass

                        logger.info("payments_expired", count=len(expired_payments))

        except Exception as exc:
            logger.exception("payment_expiry_worker_error", error=str(exc))

        await asyncio.sleep(5 * 60)  # Every 5 minutes


async def run_job_dispatch_worker() -> None:
    """
    Belt-and-suspenders job dispatcher.

    Runs every 30 seconds to catch any QUEUED jobs that were missed by
    the event-driven dispatch (e.g., during kiosk reconnection).
    """
    logger.info("job_dispatch_worker_started")

    while True:
        try:
            async with AsyncSessionFactory() as db:
                async with db.begin():
                    from app.services.job_dispatcher import JobDispatcher
                    dispatcher = JobDispatcher(db)
                    dispatched = await dispatcher.dispatch_pending_jobs()

                    if dispatched > 0:
                        logger.info("job_dispatch_worker_dispatched", count=dispatched)

        except Exception as exc:
            logger.exception("job_dispatch_worker_error", error=str(exc))

        await asyncio.sleep(30)


async def start_all_workers() -> None:
    """
    Starts all background workers as asyncio tasks.

    Called from the FastAPI lifespan context manager.
    """
    asyncio.create_task(run_cleanup_worker(), name="cleanup_worker")
    asyncio.create_task(run_heartbeat_monitor(), name="heartbeat_monitor")
    asyncio.create_task(run_payment_expiry_worker(), name="payment_expiry_worker")
    asyncio.create_task(run_job_dispatch_worker(), name="job_dispatch_worker")

    logger.info("all_background_workers_started")

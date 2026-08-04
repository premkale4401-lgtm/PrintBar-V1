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

from app.core.config import get_settings
from app.core.logging import get_logger
from app.database.session import AsyncSessionFactory

logger = get_logger(__name__)
settings = get_settings()

from typing import Any
_active_workers: list[asyncio.Task[Any]] = []


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
                            success = False
                            for attempt in range(3):
                                try:
                                    await storage_service.delete_file(
                                        bucket=file.storage_bucket,
                                        object_path=file.storage_path,
                                    )
                                    success = True
                                    break
                                except Exception as e:
                                    logger.warning("cleanup_worker_delete_retry", file_id=str(file.id), attempt=attempt, error=str(e))
                                    await asyncio.sleep(2 ** attempt)
                            
                            if not success:
                                logger.error("cleanup_worker_delete_failed", file_id=str(file.id))
                                continue

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


async def run_workflow_recovery_worker() -> None:
    """
    Recovers stuck jobs due to timeouts.
    Runs every 1 minute.
    """
    logger.info("workflow_recovery_worker_started")
    while True:
        try:
            from app.services.recovery_service import WorkflowRecoveryService
            async with AsyncSessionFactory() as db:
                service = WorkflowRecoveryService(db)
                recovered = await service.recover_stuck_jobs()
                if recovered > 0:
                    logger.info("workflow_recovery_processed", count=recovered)
        except Exception as exc:
            logger.exception("workflow_recovery_worker_error", error=str(exc))
        await asyncio.sleep(60)


async def run_simulated_kiosk_worker() -> None:
    """
    Development & Testing Worker:
    Automatically processes QUEUED or in-progress jobs when no real physical kiosk is connected.
    Simulates the print lifecycle (QUEUED -> ASSIGNED -> DOWNLOADING -> READY_TO_PRINT -> PRINTING -> COMPLETED).

    Only active when ENVIRONMENT == 'development'.
    If a real hardware kiosk connects via WebSocket, real dispatching takes over.
    """
    logger.info("simulated_kiosk_worker_started")

    while True:
        try:
            if settings.ENVIRONMENT == "development":
                from app.websocket.manager import ws_manager

                has_real_kiosks = len(ws_manager._connections) > 0
                if not has_real_kiosks:
                    active_jobs: list[tuple[str, str]] = []
                    async with AsyncSessionFactory() as db:
                        from app.repositories.print_job_repository import PrintJobRepository
                        job_repo = PrintJobRepository(db)
                        jobs = await job_repo.get_active_uncompleted_jobs()
                        active_jobs = [(str(j.id), j.status) for j in jobs]

                    for job_id_str, current_st in active_jobs:
                        import uuid
                        job_id = uuid.UUID(job_id_str)
                        logger.info("simulated_kiosk_processing_job", job_id=job_id_str, current_status=current_st)
                        logger.info("DEBUG_PAYMENT: background_worker processing job", job_id=job_id_str, current_status=current_st)

                        async def _do_transition(to_st: str):
                            async with AsyncSessionFactory() as db:
                                jr = PrintJobRepository(db)
                                await jr.transition(job_id, to_st)
                                await db.commit()

                        # Step sequence depending on starting status
                        if current_st == "QUEUED":
                            await _do_transition("ASSIGNED")
                            await asyncio.sleep(1.0)
                            current_st = "ASSIGNED"

                        if current_st == "ASSIGNED":
                            await _do_transition("DOWNLOADING")
                            await asyncio.sleep(1.2)
                            current_st = "DOWNLOADING"

                        if current_st == "DOWNLOADING":
                            await _do_transition("READY_TO_PRINT")
                            await asyncio.sleep(1.0)
                            current_st = "READY_TO_PRINT"

                        if current_st == "READY_TO_PRINT":
                            await _do_transition("PRINTING")
                            await asyncio.sleep(1.5)
                            current_st = "PRINTING"

                        if current_st == "PRINTING":
                            async with AsyncSessionFactory() as db:
                                from app.repositories.print_job_repository import PrintJobRepository
                                from app.repositories.uploaded_file_repository import (
                                    UploadedFileRepository,
                                )
                                from app.storage.service import storage_service

                                jr = PrintJobRepository(db)
                                fr = UploadedFileRepository(db)

                                job = await jr.get_by_id(job_id)
                                if job:
                                    await jr.mark_completed(job_id)
                                    if job.uploaded_file_id:
                                        uf = await fr.get_by_id(job.uploaded_file_id)
                                        if uf and not uf.is_deleted and uf.storage_path:
                                            await storage_service.delete_file(
                                                bucket=uf.storage_bucket,
                                                object_path=uf.storage_path,
                                            )
                                            await fr.mark_deleted(job.uploaded_file_id)
                                    await db.commit()
                            logger.info("simulated_kiosk_job_completed", job_id=job_id_str)

        except Exception as exc:
            logger.exception("simulated_kiosk_worker_error", error=str(exc))

        await asyncio.sleep(2)


async def start_all_workers() -> None:
    """
    Starts all background workers as asyncio tasks.

    Called from the FastAPI lifespan context manager.
    """
    _active_workers.extend([
        asyncio.create_task(run_cleanup_worker(), name="cleanup_worker"),
        asyncio.create_task(run_heartbeat_monitor(), name="heartbeat_monitor"),
        asyncio.create_task(run_payment_expiry_worker(), name="payment_expiry_worker"),
        asyncio.create_task(run_job_dispatch_worker(), name="job_dispatch_worker"),
        asyncio.create_task(run_workflow_recovery_worker(), name="workflow_recovery_worker")
    ])

    if settings.ENVIRONMENT == "development":
        _active_workers.append(
            asyncio.create_task(run_simulated_kiosk_worker(), name="simulated_kiosk_worker")
        )

    logger.info("all_background_workers_started")


async def stop_all_workers() -> None:
    """
    Gracefully cancels all active background workers and awaits their termination.
    
    Called from the FastAPI lifespan context manager during shutdown.
    """
    if not _active_workers:
        return

    logger.info("stopping_background_workers", count=len(_active_workers))
    for task in _active_workers:
        task.cancel()

    await asyncio.gather(*_active_workers, return_exceptions=True)
    _active_workers.clear()
    logger.info("background_workers_stopped")


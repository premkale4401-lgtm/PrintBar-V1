"""
PrintBar Backend — Recovery Service

Handles recovery of stuck print jobs due to network timeouts, crashes,
or payment gateway failures.

Provides an idempotent `recover_stuck_jobs` function that should be run
periodically via a background task.

Safety invariant: If a kiosk is currently WebSocket-connected and the job
is assigned to it, the recovery service will NOT intervene — the kiosk is
actively handling the job.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.logging import get_logger
from app.repositories.print_job_repository import PrintJobRepository
from app.websocket.manager import ws_manager

logger = get_logger(__name__)


class WorkflowRecoveryService:
    """
    Recovers print jobs stuck in transient states.

    Safety: always checks whether the assigned kiosk is still connected
    before recovering — avoids racing with active hardware.
    """

    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._job_repo = PrintJobRepository(db)

    async def recover_stuck_jobs(self) -> int:
        """
        Identifies and recovers jobs stuck in intermediate states based on timeouts.

        Recovery rules:
            PAYMENT_PENDING > 15 min  → CANCELLED
            ASSIGNED / DOWNLOADING / READY_TO_PRINT > 5 min (and kiosk offline) → QUEUED (retry) or FAILED
            PRINTING > 15 min (and kiosk offline)                                → FAILED (timeout)

        Returns the number of jobs processed.
        """
        now = datetime.now(tz=UTC)
        processed = 0

        jobs = await self._job_repo.get_active_uncompleted_jobs()
        if not jobs:
            return 0

        # Snapshot primitive attributes to avoid ORM lazy-loading issues.
        job_snapshots = [
            {
                "id": job.id,
                "status": job.status,
                "retry_count": job.retry_count,
                "updated_at": job.updated_at,
                "created_at": job.created_at,
                "kiosk_id": str(job.kiosk_id) if job.kiosk_id else None,
            }
            for job in jobs
        ]

        for job in job_snapshots:
            job_id = job["id"]
            status = job["status"]
            retry_count = job["retry_count"]
            assigned_kiosk_id = job["kiosk_id"]

            # Safety: if the assigned kiosk is WebSocket-connected, it is actively
            # processing the job. Do not interfere — let the kiosk complete or fail it.
            if assigned_kiosk_id and ws_manager.is_connected(assigned_kiosk_id):
                logger.debug(
                    "recovery_skipping_active_kiosk_job",
                    job_id=str(job_id),
                    kiosk_id=assigned_kiosk_id,
                    status=status,
                )
                continue

            last_update = job["updated_at"] or job["created_at"]
            if not last_update:
                continue

            if last_update.tzinfo is None:
                last_update = last_update.replace(tzinfo=UTC)

            time_elapsed = now - last_update

            try:
                # Rule 1: Payment pending > 15 mins → CANCELLED
                if status == "PAYMENT_PENDING" and time_elapsed > timedelta(minutes=15):
                    logger.warning(
                        "recovery_timeout_payment",
                        job_id=str(job_id),
                        elapsed=str(time_elapsed),
                    )
                    await self._job_repo.transition(job_id, "CANCELLED")
                    await self._db.commit()
                    processed += 1

                # Rule 2: Assigned / Downloading / Ready to Print > 5 mins
                #          with no active kiosk → retry or fail
                elif status in ("ASSIGNED", "DOWNLOADING", "READY_TO_PRINT") and time_elapsed > timedelta(minutes=5):
                    if retry_count >= 3:
                        logger.error(
                            "recovery_max_retries_exceeded",
                            job_id=str(job_id),
                            status=status,
                            kiosk_id=assigned_kiosk_id,
                        )
                        await self._job_repo.mark_failed(job_id, "MAX_RETRIES_EXCEEDED")
                    else:
                        logger.warning(
                            "recovery_stuck_job_requeued",
                            job_id=str(job_id),
                            status=status,
                            elapsed=str(time_elapsed),
                            retry_count=retry_count,
                            kiosk_id=assigned_kiosk_id,
                        )
                        await self._job_repo.transition(
                            job_id,
                            "QUEUED",
                            retry_count=retry_count + 1,
                            kiosk_id=None,
                            printer_id=None,
                        )
                    await self._db.commit()
                    processed += 1

                # Rule 3: Printing >= 15 mins with no active kiosk → FAILED (timeout)
                elif status == "PRINTING" and time_elapsed >= timedelta(minutes=15):
                    logger.error(
                        "recovery_printing_timeout",
                        job_id=str(job_id),
                        elapsed=str(time_elapsed),
                        kiosk_id=assigned_kiosk_id,
                    )
                    await self._job_repo.mark_failed(job_id, "PRINT_TIMEOUT")
                    await self._db.commit()
                    processed += 1

            except Exception as e:
                logger.error(
                    "recovery_failed_for_job",
                    job_id=str(job_id),
                    error=str(e),
                )
                await self._db.rollback()
                continue

        return processed

"""
PrintBar Backend — Recovery Service

Handles recovery of stuck print jobs due to network timeouts, crashes,
or payment gateway failures.

Provides an idempotent `recover_stuck_jobs` function that should be run
periodically via a background task.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from sqlalchemy import select, or_, and_
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.logging import get_logger
from app.models.print_job import PrintJob
from app.repositories.print_job_repository import PrintJobRepository

logger = get_logger(__name__)

class WorkflowRecoveryService:
    """
    Recovers print jobs stuck in transient states.
    """

    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._job_repo = PrintJobRepository(db)

    async def recover_stuck_jobs(self) -> int:
        """
        Identifies and recovers jobs stuck in intermediate states based on timeouts.
        Returns the number of jobs processed.
        """
        now = datetime.now(tz=UTC)
        processed = 0

        # Query active uncompleted jobs
        jobs = await self._job_repo.get_active_uncompleted_jobs()
        if not jobs:
            return 0

        # Extract primitive attributes into snapshots to avoid ORM lazy-loading/greenlet_spawn issues
        # when committing or rolling back inside the processing loop.
        job_snapshots = [
            {
                "id": job.id,
                "status": job.status,
                "retry_count": job.retry_count,
                "updated_at": job.updated_at,
                "created_at": job.created_at,
            }
            for job in jobs
        ]

        for job in job_snapshots:
            job_id = job["id"]
            status = job["status"]
            retry_count = job["retry_count"]

            # updated_at and created_at are datetime objects
            last_update = job["updated_at"] or job["created_at"]
            if not last_update:
                continue

            if last_update.tzinfo is None:
                last_update = last_update.replace(tzinfo=UTC)

            time_elapsed = now - last_update

            try:
                # Rule 1: Payment pending > 15 mins -> CANCELLED
                if status == "PAYMENT_PENDING" and time_elapsed > timedelta(minutes=15):
                    logger.warning("recovery_timeout_payment", job_id=str(job_id), elapsed=str(time_elapsed))
                    await self._job_repo.transition(job_id, "CANCELLED")
                    await self._db.commit()
                    processed += 1

                # Rule 2: Assigned / Downloading / Ready to Print > 5 mins -> Retry (Revert to QUEUED)
                elif status in ("ASSIGNED", "DOWNLOADING", "READY_TO_PRINT") and time_elapsed > timedelta(minutes=5):
                    if retry_count >= 3:
                        logger.error("recovery_max_retries_exceeded", job_id=str(job_id), status=status)
                        await self._job_repo.mark_failed(job_id, "MAX_RETRIES_EXCEEDED")
                    else:
                        logger.warning("recovery_stuck_job_requeued", job_id=str(job_id), status=status)
                        await self._job_repo.transition(
                            job_id,
                            "QUEUED",
                            retry_count=retry_count + 1,
                            kiosk_id=None,
                            printer_id=None
                        )
                    await self._db.commit()
                    processed += 1

                # Rule 3: Printing > 10 mins -> FAILED (Timeout)
                elif status == "PRINTING" and time_elapsed > timedelta(minutes=10):
                    logger.error("recovery_printing_timeout", job_id=str(job_id))
                    await self._job_repo.mark_failed(job_id, "PRINT_TIMEOUT")
                    await self._db.commit()
                    processed += 1

            except Exception as e:
                logger.error("recovery_failed_for_job", job_id=str(job_id), error=str(e))
                await self._db.rollback()
                continue

        return processed

"""
PrintBar Backend — Job Dispatcher Service

The dispatcher finds QUEUED jobs and assigns them to available kiosks.

Algorithm (simple FIFO):
    1. Find all QUEUED jobs, ordered by created_at ASC.
    2. Find all ONLINE kiosks.
    3. For each job, pick the first available kiosk (not currently printing).
    4. Send JOB_ASSIGNED message via WebSocket.
    5. Transition job to ASSIGNED.

The dispatcher runs:
    - Automatically when a job enters QUEUED status (event-driven).
    - On a 30-second background poll for missed events.
"""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.repositories.kiosk_repository import KioskRepository
from app.repositories.print_job_repository import PrintJobRepository
from app.websocket.manager import ws_manager

logger = get_logger(__name__)


class JobDispatcher:
    """
    Dispatches queued print jobs to available kiosks.
    """

    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._job_repo = PrintJobRepository(db)
        self._kiosk_repo = KioskRepository(db)

    async def dispatch_pending_jobs(self) -> int:
        """
        Dispatches all QUEUED jobs to available kiosks.

        Returns:
            Number of jobs dispatched.
        """
        queued_jobs = await self._job_repo.get_queued_jobs()
        if not queued_jobs:
            return 0

        online_kiosks = await self._kiosk_repo.get_online_kiosks()
        if not online_kiosks:
            logger.warning("dispatch_no_kiosks_available", queued=len(queued_jobs))
            return 0

        # Filter to kiosks that are actually WebSocket-connected.
        connected_kiosks = [
            k for k in online_kiosks
            if ws_manager.is_connected(str(k.id))
        ]

        if not connected_kiosks:
            return 0

        dispatched = 0
        kiosk_index = 0

        for job in queued_jobs:
            if kiosk_index >= len(connected_kiosks):
                break  # No more available kiosks.

            kiosk = connected_kiosks[kiosk_index]
            kiosk_index += 1

            # Assign job to kiosk.
            try:
                await self._job_repo.assign_to_kiosk(
                    job.id,
                    kiosk.id,
                    kiosk.id,  # Use kiosk ID as printer placeholder if no printer selected.
                )
            except Exception as exc:
                logger.warning(
                    "dispatch_assign_failed",
                    job_id=str(job.id),
                    error=str(exc),
                )
                continue

            # Build job assignment message.
            job_data = {
                "jobId": str(job.id),
                "colorMode": job.color_mode,
                "paperSize": job.paper_size,
                "copies": job.copies,
                "duplex": job.duplex,
                "pagesSelected": job.pages_selected,
                "pagesPerSheet": job.pages_per_sheet,
                "pageRange": job.page_range,
                "orientation": job.orientation,
            }

            sent = await ws_manager.send_to_kiosk(
                str(kiosk.id), "JOB_ASSIGNED", job_data
            )

            if sent:
                dispatched += 1
                logger.info(
                    "job_dispatched",
                    job_id=str(job.id),
                    kiosk_id=str(kiosk.id),
                )
            else:
                # WebSocket send failed — re-queue.
                try:
                    await self._job_repo.transition(job.id, "QUEUED")
                except Exception:
                    pass

        return dispatched

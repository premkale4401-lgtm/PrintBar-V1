"""
PrintBar Backend — Job Dispatcher Service

The dispatcher finds QUEUED jobs and assigns them to available kiosks.

Algorithm (simple FIFO):
    1. Find all QUEUED jobs, ordered by created_at ASC.
    2. Find all ONLINE kiosks that are WebSocket-connected.
    3. For each job, pick the first available kiosk.
    4. Send JOB_ASSIGNED message via WebSocket.
    5. Transition job to ASSIGNED.

The dispatcher runs:
    - Immediately when a job enters QUEUED status (event-driven — after payment verify).
    - On a JOB_DISPATCH_WORKER_INTERVAL_SECONDS background poll for missed events.

Race condition protection:
    - Only QUEUED jobs are dispatched (ASSIGNED jobs are never re-dispatched here).
    - The state machine transition from QUEUED → ASSIGNED is enforced by the DB.
    - If the WebSocket send fails, the job is reverted to QUEUED for the next cycle.
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

        Only picks up QUEUED jobs — jobs in ASSIGNED or later states are
        never touched here, preventing double-dispatch race conditions.

        Returns:
            Number of jobs dispatched in this call.
        """
        queued_jobs = await self._job_repo.get_queued_jobs()
        if not queued_jobs:
            return 0

        online_kiosks = await self._kiosk_repo.get_online_kiosks()
        if not online_kiosks:
            logger.warning("dispatch_no_kiosks_available", queued=len(queued_jobs))
            return 0

        # Filter to kiosks that are actually WebSocket-connected.
        # A kiosk might be ONLINE in DB but WS-disconnected (stale status).
        connected_kiosks = [k for k in online_kiosks if ws_manager.is_connected(str(k.id))]

        if not connected_kiosks:
            logger.debug("dispatch_no_ws_connected_kiosks", queued=len(queued_jobs))
            return 0

        dispatched = 0
        kiosk_index = 0

        # Snapshot primitive job attributes to prevent lazy-loading issues.
        job_snapshots = [
            {
                "id": j.id,
                "color_mode": j.color_mode,
                "paper_size": j.paper_size,
                "copies": j.copies,
                "duplex": j.duplex,
                "pages_selected": j.pages_selected,
                "pages_per_sheet": j.pages_per_sheet,
                "page_range": j.page_range,
                "orientation": j.orientation,
            }
            for j in queued_jobs
        ]

        for job in job_snapshots:
            if kiosk_index >= len(connected_kiosks):
                break  # No more available kiosks.

            kiosk = connected_kiosks[kiosk_index]
            kiosk_index += 1

            job_id = job["id"]

            # Transition QUEUED → ASSIGNED atomically.
            try:
                await self._job_repo.assign_to_kiosk(
                    job_id,
                    kiosk.id,
                    kiosk.id,  # Use kiosk ID as printer placeholder if no printer selected.
                )
            except Exception as exc:
                logger.warning(
                    "dispatch_assign_failed",
                    job_id=str(job_id),
                    kiosk_id=str(kiosk.id),
                    error=str(exc),
                )
                continue

            # Build job assignment message.
            job_data = {
                "jobId": str(job_id),
                "colorMode": job["color_mode"],
                "paperSize": job["paper_size"],
                "copies": job["copies"],
                "duplex": job["duplex"],
                "pagesSelected": job["pages_selected"],
                "pagesPerSheet": job["pages_per_sheet"],
                "pageRange": job["page_range"],
                "orientation": job["orientation"],
            }

            sent = await ws_manager.send_to_kiosk(str(kiosk.id), "JOB_ASSIGNED", job_data)

            if sent:
                dispatched += 1
                logger.info(
                    "job_dispatched",
                    job_id=str(job_id),
                    kiosk_id=str(kiosk.id),
                )
            else:
                # WebSocket send failed — re-queue so next poll picks it up.
                logger.warning(
                    "dispatch_ws_send_failed_reverting_to_queued",
                    job_id=str(job_id),
                    kiosk_id=str(kiosk.id),
                )
                try:
                    await self._job_repo.transition(job_id, "QUEUED")
                except Exception as revert_exc:
                    logger.error(
                        "dispatch_revert_to_queued_failed",
                        job_id=str(job_id),
                        error=str(revert_exc),
                    )

        return dispatched

"""
PrintBar Backend — Report Service

Aggregated analytics and reporting queries.
Used by the admin dashboard and analytics endpoints.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.kiosk import Kiosk
from app.models.payment import Payment
from app.models.print_job import PrintJob

logger = get_logger(__name__)


class ReportService:
    """Generates analytics reports from database aggregates."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_analytics(
        self,
        *,
        days: int = 30,
    ) -> dict:
        """
        Returns aggregated analytics for the given date range.

        Args:
            days: Number of past days to include.

        Returns:
            Dict with revenue, job counts, kiosk stats.
        """
        since = (datetime.now(tz=UTC) - timedelta(days=days)).isoformat()

        # Total revenue from verified payments.
        revenue_result = await self._db.execute(
            select(func.sum(Payment.amount_inr)).where(
                Payment.status == "VERIFIED",
                Payment.created_at >= since,
            )
        )
        total_revenue = float(revenue_result.scalar() or Decimal("0"))

        # Total jobs by status.
        jobs_result = await self._db.execute(
            select(PrintJob.status, func.count(PrintJob.id))
            .where(PrintJob.created_at >= since)
            .group_by(PrintJob.status)
        )
        jobs_by_status = {row[0]: row[1] for row in jobs_result.all()}

        # Total jobs.
        total_jobs = sum(jobs_by_status.values())
        completed_jobs = jobs_by_status.get("COMPLETED", 0)

        # Online kiosks right now.
        online_result = await self._db.execute(
            select(func.count(Kiosk.id)).where(
                Kiosk.is_active.is_(True),
                Kiosk.status.in_(["ONLINE", "PRINTING"]),
            )
        )
        online_kiosks = online_result.scalar() or 0

        total_kiosks_result = await self._db.execute(
            select(func.count(Kiosk.id)).where(Kiosk.is_active.is_(True))
        )
        total_kiosks = total_kiosks_result.scalar() or 0

        # Average revenue per job.
        avg_revenue = round(total_revenue / max(completed_jobs, 1), 2)

        return {
            "periodDays": days,
            "since": since,
            "totalRevenueInr": round(total_revenue, 2),
            "totalJobs": total_jobs,
            "completedJobs": completed_jobs,
            "jobsByStatus": jobs_by_status,
            "avgRevenuePerJobInr": avg_revenue,
            "onlineKiosks": online_kiosks,
            "totalKiosks": total_kiosks,
        }

    async def get_daily_revenue(self, *, days: int = 30) -> list[dict]:
        """
        Returns daily revenue for the past N days.

        Returns a list of {date, revenue_inr, job_count} dicts.
        """
        results = []
        now = datetime.now(tz=UTC)

        for i in range(days - 1, -1, -1):
            day_start = (now - timedelta(days=i)).replace(hour=0, minute=0, second=0, microsecond=0)
            day_end = day_start + timedelta(days=1)

            revenue_result = await self._db.execute(
                select(func.sum(Payment.amount_inr)).where(
                    Payment.status == "VERIFIED",
                    Payment.created_at >= day_start.isoformat(),
                    Payment.created_at < day_end.isoformat(),
                )
            )
            revenue = float(revenue_result.scalar() or Decimal("0"))

            jobs_result = await self._db.execute(
                select(func.count(PrintJob.id)).where(
                    PrintJob.created_at >= day_start.isoformat(),
                    PrintJob.created_at < day_end.isoformat(),
                )
            )
            job_count = jobs_result.scalar() or 0

            results.append({
                "date": day_start.strftime("%Y-%m-%d"),
                "revenueInr": round(revenue, 2),
                "jobCount": job_count,
            })

        return results

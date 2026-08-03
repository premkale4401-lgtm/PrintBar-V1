"""
PrintBar Backend — Pricing Rule Repository

Data access for PricingRule records.
Pricing history is preserved — old rules are never deleted, only deactivated.
"""
from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.pricing_rule import PricingRule

logger = get_logger(__name__)

class PricingRuleRepository:
    """Repository for PricingRule records."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_active(self) -> PricingRule | None:
        """Returns the currently active pricing rule."""
        result = await self._db.execute(
            select(PricingRule).where(PricingRule.is_active.is_(True)).limit(1)
        )
        return result.scalar_one_or_none()

    async def get_all(self) -> list[PricingRule]:
        """Returns all pricing rules (history included)."""
        result = await self._db.execute(
            select(PricingRule).order_by(PricingRule.created_at.desc())
        )
        return list(result.scalars().all())

    async def create_rule(
        self,
        *,
        name: str,
        bw_price_inr: Decimal,
        color_price_inr: Decimal,
        a3_multiplier: Decimal = Decimal("1.75"),
        legal_multiplier: Decimal = Decimal("1.25"),
        duplex_discount: Decimal = Decimal("0.00"),
        gst_percent: Decimal = Decimal("18.00"),
        notes: str | None = None,
    ) -> PricingRule:
        """
        Creates a new active pricing rule and deactivates the previous one.

        Old rules are retained for pricing history and dispute resolution.
        """
        now = datetime.now(tz=UTC).isoformat()

        # Deactivate current rule.
        await self._db.execute(
            update(PricingRule)
            .where(PricingRule.is_active.is_(True))
            .values(is_active=False, valid_until=now)
        )

        rule = PricingRule(
            name=name,
            bw_price_inr=bw_price_inr,
            color_price_inr=color_price_inr,
            a3_multiplier=a3_multiplier,
            legal_multiplier=legal_multiplier,
            duplex_discount=duplex_discount,
            gst_percent=gst_percent,
            is_active=True,
            valid_from=now,
            notes=notes,
        )
        self._db.add(rule)
        await self._db.flush()
        logger.info("pricing_rule_created", rule_id=str(rule.id), name=name)
        return rule

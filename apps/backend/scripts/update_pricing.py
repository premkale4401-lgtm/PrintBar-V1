"""
PrintBar — Set Flat Inclusive Pricing (No GST)

Sets:
    BW    = Rs.2.00 per page  (final price, GST-inclusive)
    Color = Rs.10.00 per page (final price, GST-inclusive)
    GST   = 0%  (prices already include everything)

Run this script once:
    python -m scripts.update_pricing
"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from decimal import Decimal
from sqlalchemy import select

from app.database.session import AsyncSessionFactory
from app.models.pricing_rule import PricingRule
from app.core.logging import configure_logging, get_logger

configure_logging()
logger = get_logger(__name__)


async def main() -> None:
    logger.info("update_pricing_start")

    async with AsyncSessionFactory() as session:
        async with session.begin():
            result = await session.execute(
                select(PricingRule)
                .where(PricingRule.is_active.is_(True))
                .order_by(PricingRule.created_at.desc())
                .limit(1)
            )
            rule = result.scalar_one_or_none()

            if rule is None:
                logger.error("no_active_pricing_rule_found")
                print("ERROR: No active pricing rule found. Run seed first.")
                return

            rule.bw_price_inr = Decimal("2.00")
            rule.color_price_inr = Decimal("10.00")
            rule.gst_percent = Decimal("0.00")   # Prices are already all-inclusive
            rule.name = "PrintBar Flat Pricing (Rs.2 BW / Rs.10 Color, 0% GST)"
            rule.notes = "Final prices: Rs.2/page BW, Rs.10/page Color. GST set to 0 as prices are all-inclusive."

            logger.info("pricing_updated", rule_id=str(rule.id))
            print("Updated pricing:")
            print("  BW    = Rs.2.00 per page (final, all-inclusive)")
            print("  Color = Rs.10.00 per page (final, all-inclusive)")
            print("  GST   = 0% (prices already include everything)")

    logger.info("update_pricing_complete")


if __name__ == "__main__":
    asyncio.run(main())

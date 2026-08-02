"""
PrintBar Backend — Database Seed Script

Creates initial data required for the application to function.

Seeds:
    1. Initial pricing rule (BW=₹3/sheet, Color=₹10/sheet, GST=18%)
    2. Super admin user (from environment variables — never hardcoded)

Usage:
    python -m scripts.seed

Environment variables required:
    DATABASE_URL
    SEED_ADMIN_EMAIL
    SEED_ADMIN_PASSWORD
    SEED_ADMIN_NAME
"""

import asyncio
import os
import sys
from datetime import UTC, datetime

# Add parent directory to path for module resolution.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select

from app.core.security import password_hasher
from app.database.session import AsyncSessionFactory
from app.models.pricing_rule import PricingRule
from app.models.user import User
from app.core.constants import ROLE_SUPER_ADMIN
from app.core.logging import configure_logging, get_logger

configure_logging()
logger = get_logger(__name__)


INITIAL_PRICING = {
    "name": "PrintBar Flat Pricing (Rs.2 BW / Rs.10 Color, 0% GST)",
    "bw_price_inr": "2.00",
    "color_price_inr": "10.00",
    "a3_multiplier": "1.75",
    "legal_multiplier": "1.25",
    "duplex_discount": "0.00",
    "gst_percent": "0.00",   # Prices are already all-inclusive (no separate GST)
    "is_active": True,
    "valid_from": datetime.now(tz=UTC).isoformat(),
    "valid_until": None,
    "notes": "Final prices: Rs.2/page BW, Rs.10/page Color. GST set to 0 as prices are all-inclusive.",
}


async def seed_pricing(session) -> None:  # type: ignore[no-untyped-def]
    """Seeds the initial pricing rule if none exists."""
    result = await session.execute(
        select(PricingRule).where(PricingRule.is_active.is_(True))
    )
    existing = result.scalar_one_or_none()

    if existing:
        logger.info("pricing_already_seeded", rule_id=str(existing.id))
        return

    from decimal import Decimal

    rule = PricingRule(
        name=INITIAL_PRICING["name"],
        bw_price_inr=Decimal(INITIAL_PRICING["bw_price_inr"]),  # type: ignore[arg-type]
        color_price_inr=Decimal(INITIAL_PRICING["color_price_inr"]),  # type: ignore[arg-type]
        a3_multiplier=Decimal(INITIAL_PRICING["a3_multiplier"]),  # type: ignore[arg-type]
        legal_multiplier=Decimal(INITIAL_PRICING["legal_multiplier"]),  # type: ignore[arg-type]
        duplex_discount=Decimal(INITIAL_PRICING["duplex_discount"]),  # type: ignore[arg-type]
        gst_percent=Decimal(INITIAL_PRICING["gst_percent"]),  # type: ignore[arg-type]
        is_active=True,
        valid_from=INITIAL_PRICING["valid_from"],  # type: ignore[arg-type]
        notes=INITIAL_PRICING["notes"],  # type: ignore[arg-type]
    )
    session.add(rule)
    logger.info("pricing_seeded", name=rule.name)


async def seed_super_admin(session) -> None:  # type: ignore[no-untyped-def]
    """
    Seeds the initial super admin user from environment variables.

    Required environment variables:
        SEED_ADMIN_EMAIL
        SEED_ADMIN_PASSWORD
        SEED_ADMIN_NAME
    """
    email = os.environ.get("SEED_ADMIN_EMAIL")
    password = os.environ.get("SEED_ADMIN_PASSWORD")
    name = os.environ.get("SEED_ADMIN_NAME", "Super Admin")

    if not email or not password:
        logger.warning(
            "super_admin_seed_skipped",
            reason="SEED_ADMIN_EMAIL and SEED_ADMIN_PASSWORD not set",
        )
        return

    # Validate password policy.
    errors = password_hasher.validate_admin_password(password)
    if errors:
        logger.error("seed_admin_password_policy_violation", errors=errors)
        raise ValueError(f"Admin password policy violation: {'; '.join(errors)}")

    result = await session.execute(select(User).where(User.email == email))
    existing = result.scalar_one_or_none()

    if existing:
        logger.info("super_admin_already_exists", email=email)
        return

    user = User(
        email=email,
        name=name,
        password_hash=password_hasher.hash(password),
        role=ROLE_SUPER_ADMIN,
        is_active=True,
    )
    session.add(user)
    logger.info("super_admin_seeded", email=email, name=name)


async def main() -> None:
    """Runs all seed operations in a single transaction."""
    logger.info("seed_starting")

    async with AsyncSessionFactory() as session:
        async with session.begin():
            await seed_pricing(session)
            await seed_super_admin(session)

    logger.info("seed_complete")


if __name__ == "__main__":
    asyncio.run(main())

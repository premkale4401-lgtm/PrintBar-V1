#!/usr/bin/env python3
"""
PrintBar Backend — Database Seed Script

Idempotent seed script for local development.
Populates the database with the minimum data required for a working dev environment:
  - Default pricing rules
  - Default super admin account (if not present)

Usage:
    python scripts/seed_db.py

Never run this in production. Use migration 0002 instead.
"""
from __future__ import annotations

import asyncio
import os
import sys

# Ensure backend app is importable.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select


async def seed():
    from app.core.security import password_hasher
    from app.database.session import AsyncSessionFactory
    from app.models.pricing_rule import PricingRule
    from app.models.user import User

    async with AsyncSessionFactory() as db:
        # Seed pricing rule.
        result = await db.execute(select(PricingRule).where(PricingRule.is_active.is_(True)))
        existing = result.scalar_one_or_none()
        if not existing:
            rule = PricingRule(
                name="Default Pricing — Local Dev",
                bw_price_inr=Decimal("2.00"),
                color_price_inr=Decimal("10.00"),
                a3_multiplier=Decimal("1.75"),
                legal_multiplier=Decimal("1.25"),
                duplex_discount=Decimal("0.10"),
                gst_percent=Decimal("18.00"),
                is_active=True,
                valid_from=datetime.now(tz=UTC).isoformat(),
                notes="Seeded by seed_db.py for local development.",
            )
            db.add(rule)
            print("[seed] Created default pricing rule.")
        else:
            print(f"[seed] Pricing rule already exists: {existing.name} — skipping.")

        # Seed super admin (only if ADMIN_EMAIL env var is set).
        admin_email = os.getenv("SEED_ADMIN_EMAIL")
        admin_password = os.getenv("SEED_ADMIN_PASSWORD")
        if admin_email and admin_password:
            result = await db.execute(select(User).where(User.email == admin_email.lower()))
            existing_user = result.scalar_one_or_none()
            if not existing_user:
                hashed = password_hasher.hash(admin_password)
                user = User(
                    email=admin_email.lower(),
                    name="Super Admin",
                    password_hash=hashed,
                    role="SUPER_ADMIN",
                    is_active=True,
                )
                db.add(user)
                print(f"[seed] Created super admin: {admin_email}")
            else:
                print(f"[seed] Admin already exists: {admin_email} — skipping.")
        else:
            print("[seed] SEED_ADMIN_EMAIL/SEED_ADMIN_PASSWORD not set — skipping admin creation.")

        await db.commit()
        print("[seed] Done.")

if __name__ == "__main__":
    asyncio.run(seed())

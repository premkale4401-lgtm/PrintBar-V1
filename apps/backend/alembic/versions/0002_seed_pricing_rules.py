"""Seed default pricing rules

Revision ID: 0002_seed_pricing_rules
Revises: 0001_initial_schema
Create Date: 2026-08-03

Seeds the initial pricing rules required for the pricing engine to work.
All amounts in INR. Idempotent — skips if a rule already exists.
"""

from __future__ import annotations
from collections.abc import Sequence
from datetime import UTC, datetime
import uuid
import sqlalchemy as sa
from alembic import op

revision: str = "0002_seed_pricing_rules"
down_revision: str | None = "0001_initial_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

NOW = datetime.now(tz=UTC).isoformat()


def upgrade() -> None:
    conn = op.get_bind()

    # Check if any pricing rule already exists (idempotent).
    result = conn.execute(sa.text("SELECT COUNT(*) FROM pricing_rules"))
    count = result.scalar()
    if count and count > 0:
        return  # Already seeded — skip.

    conn.execute(
        sa.text("""
        INSERT INTO pricing_rules (
            id, name, bw_price_inr, color_price_inr, a3_multiplier,
            legal_multiplier, duplex_discount, gst_percent,
            is_active, valid_from, notes, created_at, updated_at
        ) VALUES (
            :id, :name, :bw, :color, :a3_mult,
            :legal_mult, :duplex_disc, :gst,
            TRUE, :valid_from, :notes, :now, :now
        )
        """),
        {
            "id": str(uuid.uuid4()),
            "name": "Default Pricing — Launch",
            "bw": "2.00",
            "color": "10.00",
            "a3_mult": "1.75",
            "legal_mult": "1.25",
            "duplex_disc": "0.10",
            "gst": "18.00",
            "valid_from": NOW,
            "notes": "Default pricing seeded at first deployment. B&W: Rs 2/page, Color: Rs 10/page, GST: 18%, Duplex discount: 10%.",
            "now": NOW,
        },
    )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("DELETE FROM pricing_rules WHERE name = 'Default Pricing — Launch'"))

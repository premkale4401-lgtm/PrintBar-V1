"""
PrintBar Backend — PricingRule Model

Stores the pricing configuration for the PrintBar platform.
All pricing is owned by the backend. The frontend never calculates prices.

Only one rule is "active" at a time. Changing prices creates a new rule
with the old rule's valid_until set to now. This preserves pricing history
for dispute resolution and analytics.

Admin actions on pricing are logged in audit_logs.
"""

from decimal import Decimal

from sqlalchemy import Boolean, Enum, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.constants import (
    COLOR_MODE_BW,
    COLOR_MODE_COLOR,
    PAPER_SIZE_A3,
    PAPER_SIZE_A4,
    PAPER_SIZE_LEGAL,
    PAPER_SIZE_LETTER,
)
from app.database.base import PrintBarBase


class PricingRule(PrintBarBase):
    """
    Pricing configuration for print jobs.

    Columns:
        name:               Human-readable name for this pricing configuration.
        bw_price_inr:       Per-sheet price for B&W printing in INR.
        color_price_inr:    Per-sheet price for color printing in INR.
        a3_multiplier:      Price multiplier for A3 paper.
        legal_multiplier:   Price multiplier for Legal paper.
        duplex_discount:    Discount percentage for duplex jobs (0.00 to 1.00).
        gst_percent:        GST percentage applied on subtotal (e.g., 18.00).
        is_active:          True for the currently active pricing rule.
        valid_from:         UTC timestamp from which this rule is effective.
        valid_until:        UTC timestamp after which this rule is superseded.
        notes:              Admin notes about the pricing change.

    Constraints:
        - Only one rule should be active at a time.
        - The backend enforces this by deactivating the previous rule when
          a new one is activated.
    """

    __tablename__ = "pricing_rules"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    bw_price_inr: Mapped[Decimal] = mapped_column(
        Numeric(8, 2), nullable=False
    )
    color_price_inr: Mapped[Decimal] = mapped_column(
        Numeric(8, 2), nullable=False
    )
    a3_multiplier: Mapped[Decimal] = mapped_column(
        Numeric(4, 2), nullable=False, default=Decimal("1.75")
    )
    legal_multiplier: Mapped[Decimal] = mapped_column(
        Numeric(4, 2), nullable=False, default=Decimal("1.25")
    )
    duplex_discount: Mapped[Decimal] = mapped_column(
        Numeric(4, 2), nullable=False, default=Decimal("0.00")
    )
    gst_percent: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False, default=Decimal("18.00")
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    valid_from: Mapped[str] = mapped_column(String(50), nullable=False)
    valid_until: Mapped[str | None] = mapped_column(String(50), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

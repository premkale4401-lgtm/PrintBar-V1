"""
PrintBar Backend — Pricing Engine

The backend is the sole authority for all price calculations.
The frontend NEVER computes prices. All pricing UI data comes from this service.

Pricing formula:
    sheets = ceil(pages_selected / pages_per_sheet) * copies
    paper_multiplier = 1.0 (A4/Letter) | a3_multiplier | legal_multiplier
    base_price = bw_price (or color_price) * sheets * paper_multiplier
    duplex_discount = base_price * duplex_discount_rate
    subtotal = base_price - duplex_discount
    gst = subtotal * (gst_percent / 100)
    total = subtotal + gst

All amounts are in Indian Rupees (INR), rounded to 2 decimal places.
Minimum total is ₹1.00 (Easebuzz minimum transaction).
"""

from __future__ import annotations

import math
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import (
    COLOR_MODE_COLOR,
    PAPER_SIZE_A3,
    PAPER_SIZE_LEGAL,
)
from app.core.logging import get_logger
from app.models.pricing_rule import PricingRule

logger = get_logger(__name__)

# Minimum transaction amount enforced by Easebuzz.
MINIMUM_TOTAL_INR = Decimal("1.00")


class PriceCalculation:
    """
    Immutable result of a price calculation.

    Attributes:
        pages_to_print:   Actual pages that will be printed.
        sheets:           Physical sheets of paper consumed.
        price_per_sheet:  Per-sheet price before multipliers.
        subtotal_inr:     Pre-GST total.
        gst_inr:          GST amount.
        total_inr:        Final amount the user pays.
        gst_percent:      GST rate applied.
        currency:         Always "INR".
        breakdown:        Human-readable breakdown dict for the frontend.
    """

    def __init__(
        self,
        pages_to_print: int,
        sheets: int,
        price_per_sheet: Decimal,
        subtotal_inr: Decimal,
        gst_inr: Decimal,
        total_inr: Decimal,
        gst_percent: Decimal,
    ) -> None:
        self.pages_to_print = pages_to_print
        self.sheets = sheets
        self.price_per_sheet = price_per_sheet
        self.subtotal_inr = subtotal_inr
        self.gst_inr = gst_inr
        self.total_inr = total_inr
        self.gst_percent = gst_percent
        self.currency = "INR"

    def to_dict(self) -> dict:
        return {
            "subtotalInr": str(self.subtotal_inr),
            "gstInr": str(self.gst_inr),
            "totalInr": str(self.total_inr),
            "gstPercent": str(self.gst_percent),
            "sheets": self.sheets,
            "pagesToPrint": self.pages_to_print,
            "pricePerSheetInr": str(self.price_per_sheet),
            "currency": self.currency,
        }


class PricingService:
    """
    Calculates print job prices using the active pricing rule from the database.

    Responsibilities:
        - Load the active pricing rule.
        - Apply the pricing formula.
        - Return a PriceCalculation result.

    Args:
        db: Async SQLAlchemy session.
    """

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_active_rule(self) -> PricingRule:
        """
        Loads the currently active pricing rule.

        Raises:
            RuntimeError: If no active pricing rule exists in the database.
        """
        result = await self._db.execute(
            select(PricingRule)
            .where(PricingRule.is_active.is_(True))
            .order_by(PricingRule.created_at.desc())
            .limit(1)
        )
        rule = result.scalar_one_or_none()
        if rule is None:
            logger.error("no_active_pricing_rule_found")
            raise RuntimeError(
                "No active pricing rule configured. Run the seed script."
            )
        return rule

    async def calculate(
        self,
        pages_selected: int,
        color_mode: str,
        paper_size: str,
        copies: int,
        duplex: bool,
        pages_per_sheet: int = 1,
    ) -> PriceCalculation:
        """
        Calculates the price for a print job.

        Args:
            pages_selected:  Number of pages to print.
            color_mode:      "BW" or "COLOR".
            paper_size:      "A4", "A3", "LETTER", or "LEGAL".
            copies:          Number of copies.
            duplex:          True for double-sided printing.
            pages_per_sheet: Pages printed per physical sheet (1, 2, 4, or 6).

        Returns:
            PriceCalculation with breakdown.
        """
        rule = await self.get_active_rule()
        return self._compute(
            rule=rule,
            pages_selected=pages_selected,
            color_mode=color_mode,
            paper_size=paper_size,
            copies=copies,
            duplex=duplex,
            pages_per_sheet=pages_per_sheet,
        )

    def calculate_with_rule(
        self,
        rule: PricingRule,
        pages_selected: int,
        color_mode: str,
        paper_size: str,
        copies: int,
        duplex: bool,
        pages_per_sheet: int = 1,
    ) -> PriceCalculation:
        """
        Synchronous calculation using an already-loaded rule.

        Used internally when the rule is already fetched (avoids double DB hit).
        """
        return self._compute(
            rule=rule,
            pages_selected=pages_selected,
            color_mode=color_mode,
            paper_size=paper_size,
            copies=copies,
            duplex=duplex,
            pages_per_sheet=pages_per_sheet,
        )

    def _compute(
        self,
        rule: PricingRule,
        pages_selected: int,
        color_mode: str,
        paper_size: str,
        copies: int,
        duplex: bool,
        pages_per_sheet: int,
    ) -> PriceCalculation:
        """
        Core pricing formula (pure, no I/O).

        Formula:
            sheets_per_copy = ceil(pages_selected / pages_per_sheet)
            total_sheets = sheets_per_copy * copies
            paper_multiplier = 1.0 (A4/Letter) | a3_multiplier | legal_multiplier
            price_per_sheet = bw_price or color_price
            base_price = price_per_sheet * total_sheets * paper_multiplier
            duplex_savings = base_price * duplex_discount
            subtotal = base_price - duplex_savings
            gst = subtotal * (gst_percent / 100)
            total = subtotal + gst  (minimum ₹1.00)
        """
        # Determine per-sheet price.
        if color_mode == COLOR_MODE_COLOR:
            base_price_per_sheet = Decimal(str(rule.color_price_inr))
        else:
            base_price_per_sheet = Decimal(str(rule.bw_price_inr))

        # Paper size multiplier.
        if paper_size == PAPER_SIZE_A3:
            paper_multiplier = Decimal(str(rule.a3_multiplier))
        elif paper_size == PAPER_SIZE_LEGAL:
            paper_multiplier = Decimal(str(rule.legal_multiplier))
        else:
            paper_multiplier = Decimal("1.00")

        effective_price_per_sheet = (
            base_price_per_sheet * paper_multiplier
        ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        # Sheet count.
        sheets_per_copy = math.ceil(pages_selected / pages_per_sheet)
        total_sheets = sheets_per_copy * copies

        # Duplex halves sheets (round up — last page may be single-sided).
        if duplex:
            total_sheets = math.ceil(total_sheets / 2)

        base_total = effective_price_per_sheet * Decimal(total_sheets)

        # Duplex discount on base price.
        duplex_discount_rate = Decimal(str(rule.duplex_discount))
        if duplex and duplex_discount_rate > Decimal("0"):
            savings = (base_total * duplex_discount_rate).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
            subtotal = base_total - savings
        else:
            subtotal = base_total

        subtotal = subtotal.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        # GST.
        gst_rate = Decimal(str(rule.gst_percent)) / Decimal("100")
        gst = (subtotal * gst_rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        total = (subtotal + gst).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        # Enforce minimum.
        if total < MINIMUM_TOTAL_INR:
            total = MINIMUM_TOTAL_INR
            # Recompute gst from enforced minimum for consistency.
            subtotal = (total / (Decimal("1") + gst_rate)).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
            gst = total - subtotal

        logger.info(
            "price_calculated",
            pages=pages_selected,
            color_mode=color_mode,
            paper_size=paper_size,
            copies=copies,
            duplex=duplex,
            sheets=total_sheets,
            subtotal=str(subtotal),
            gst=str(gst),
            total=str(total),
        )

        return PriceCalculation(
            pages_to_print=pages_selected,
            sheets=total_sheets,
            price_per_sheet=effective_price_per_sheet,
            subtotal_inr=subtotal,
            gst_inr=gst,
            total_inr=total,
            gst_percent=Decimal(str(rule.gst_percent)),
        )

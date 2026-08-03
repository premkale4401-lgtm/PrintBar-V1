"""
PrintBar Backend — Pricing Service Unit Tests

Tests for the PricingService business logic:
    - BW per-page calculation
    - Color per-page calculation
    - GST application
    - to_dict() response structure
    - Service with mock DB
"""
from __future__ import annotations

from decimal import Decimal

import pytest

from app.services.pricing_service import PriceCalculation

# ─── PriceCalculation Dataclass ───────────────────────────────────────────────

def test_price_calculation_to_dict_has_required_keys():
    """to_dict() must return all keys expected by the frontend payment payload."""
    calc = PriceCalculation(
        pages_to_print=5,
        sheets=5,
        price_per_sheet=Decimal("2.00"),
        subtotal_inr=Decimal("10.00"),
        gst_inr=Decimal("1.80"),
        total_inr=Decimal("11.80"),
        gst_percent=Decimal("18.00"),
    )
    d = calc.to_dict()
    required_keys = {"subtotalInr", "gstInr", "totalInr", "gstPercent", "sheets", "pagesToPrint"}
    assert required_keys.issubset(d.keys())


def test_price_calculation_to_dict_amounts_are_strings():
    """Decimal amounts in to_dict() must be strings for JSON serialization safety."""
    calc = PriceCalculation(
        pages_to_print=5,
        sheets=5,
        price_per_sheet=Decimal("2.00"),
        subtotal_inr=Decimal("10.00"),
        gst_inr=Decimal("1.80"),
        total_inr=Decimal("11.80"),
        gst_percent=Decimal("18.00"),
    )
    d = calc.to_dict()
    assert isinstance(d["subtotalInr"], str)
    assert isinstance(d["gstInr"], str)
    assert isinstance(d["totalInr"], str)


def test_price_calculation_currency_is_inr():
    """currency field must always be 'INR'."""
    calc = PriceCalculation(
        pages_to_print=1,
        sheets=1,
        price_per_sheet=Decimal("2.00"),
        subtotal_inr=Decimal("2.00"),
        gst_inr=Decimal("0.36"),
        total_inr=Decimal("2.36"),
        gst_percent=Decimal("18.00"),
    )
    assert calc.currency == "INR"


# ─── PricingService Integration Tests (real DB via conftest) ──────────────────

@pytest.mark.asyncio
async def test_pricing_service_bw_calculation(db_session):
    """PricingService must correctly calculate BW pricing with GST."""
    from datetime import UTC, datetime

    from app.models.pricing_rule import PricingRule
    from app.services.pricing_service import PricingService

    rule = PricingRule(
        name="BW Test Rule",
        bw_price_inr=Decimal("2.00"),
        color_price_inr=Decimal("10.00"),
        a3_multiplier=Decimal("1.75"),
        legal_multiplier=Decimal("1.25"),
        duplex_discount=Decimal("0.00"),
        gst_percent=Decimal("18.00"),
        is_active=True,
        valid_from=datetime.now(tz=UTC).isoformat(),
    )
    db_session.add(rule)
    await db_session.flush()

    service = PricingService(db_session)
    calc = await service.calculate(
        pages_selected=5,
        color_mode="BW",
        paper_size="A4",
        copies=2,
        duplex=False,
        pages_per_sheet=1,
    )

    # 5 pages × ₹2.00 × 2 copies = ₹20.00 subtotal
    assert calc.subtotal_inr == Decimal("20.00")
    assert calc.total_inr > calc.subtotal_inr  # GST adds to total
    assert calc.gst_inr == Decimal("3.60")     # 18% of 20.00
    assert calc.total_inr == Decimal("23.60")


@pytest.mark.asyncio
async def test_pricing_service_color_calculation(db_session):
    """PricingService must apply color pricing for COLOR mode."""
    from datetime import UTC, datetime

    from app.models.pricing_rule import PricingRule
    from app.services.pricing_service import PricingService

    rule = PricingRule(
        name="Color Test Rule",
        bw_price_inr=Decimal("2.00"),
        color_price_inr=Decimal("10.00"),
        a3_multiplier=Decimal("1.75"),
        legal_multiplier=Decimal("1.25"),
        duplex_discount=Decimal("0.00"),
        gst_percent=Decimal("0.00"),
        is_active=True,
        valid_from=datetime.now(tz=UTC).isoformat(),
    )
    db_session.add(rule)
    await db_session.flush()

    service = PricingService(db_session)
    calc = await service.calculate(
        pages_selected=3,
        color_mode="COLOR",
        paper_size="A4",
        copies=1,
        duplex=False,
        pages_per_sheet=1,
    )

    # 3 pages × ₹10.00 × 1 copy = ₹30.00, no GST
    assert calc.subtotal_inr == Decimal("30.00")
    assert calc.gst_inr == Decimal("0.00")
    assert calc.total_inr == Decimal("30.00")


@pytest.mark.asyncio
async def test_pricing_service_no_active_rule_raises(db_session):
    """PricingService must raise RuntimeError when no active rule exists."""
    from sqlalchemy import update

    from app.models.pricing_rule import PricingRule
    from app.services.pricing_service import PricingService

    # Deactivate any existing rules.
    await db_session.execute(
        update(PricingRule).values(is_active=False)
    )
    await db_session.flush()

    service = PricingService(db_session)
    with pytest.raises(RuntimeError, match="No active pricing rule"):
        await service.calculate(
            pages_selected=1,
            color_mode="BW",
            paper_size="A4",
            copies=1,
            duplex=False,
        )

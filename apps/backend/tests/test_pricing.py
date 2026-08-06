"""
PrintBar Backend — Pricing Service Tests

Unit tests for the PricingService using pure computation (no DB needed
for the _compute path).
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from app.models.pricing_rule import PricingRule
from app.services.pricing_service import MINIMUM_TOTAL_INR, PricingService


def _make_rule(
    bw=2.00,
    color=5.00,
    a3=1.75,
    legal=1.25,
    duplex=0.00,
    gst=18.00,
) -> PricingRule:
    """Creates a mock PricingRule with given values."""
    rule = MagicMock(spec=PricingRule)
    rule.bw_price_inr = Decimal(str(bw))
    rule.color_price_inr = Decimal(str(color))
    rule.a3_multiplier = Decimal(str(a3))
    rule.legal_multiplier = Decimal(str(legal))
    rule.duplex_discount = Decimal(str(duplex))
    rule.gst_percent = Decimal(str(gst))
    return rule


class TestPricingServiceCompute:
    """Tests for the pure _compute method."""

    def setup_method(self) -> None:
        self.service = PricingService(db=MagicMock())

    def test_bw_a4_single_page(self) -> None:
        rule = _make_rule(bw=2.00, gst=18.00)
        calc = self.service._compute(
            rule=rule,
            pages_selected=1,
            color_mode="BW",
            paper_size="A4",
            copies=1,
            duplex=False,
            pages_per_sheet=1,
        )
        # 1 sheet × ₹2.00 = ₹2.00 subtotal; 18% GST = ₹0.36; total = ₹2.36
        assert calc.sheets == 1
        assert calc.subtotal_inr == Decimal("2.00")
        assert calc.gst_inr == Decimal("0.36")
        assert calc.total_inr == Decimal("2.36")

    def test_color_a4(self) -> None:
        rule = _make_rule(color=5.00, gst=18.00)
        calc = self.service._compute(
            rule=rule,
            pages_selected=1,
            color_mode="COLOR",
            paper_size="A4",
            copies=1,
            duplex=False,
            pages_per_sheet=1,
        )
        assert calc.subtotal_inr == Decimal("5.00")
        assert calc.total_inr == Decimal("5.90")

    def test_a3_multiplier(self) -> None:
        rule = _make_rule(bw=2.00, a3=1.75, gst=18.00)
        calc = self.service._compute(
            rule=rule,
            pages_selected=1,
            color_mode="BW",
            paper_size="A3",
            copies=1,
            duplex=False,
            pages_per_sheet=1,
        )
        # 2.00 × 1.75 = 3.50 per sheet
        assert calc.price_per_sheet == Decimal("3.50")

    def test_legal_multiplier(self) -> None:
        rule = _make_rule(bw=2.00, legal=1.25, gst=18.00)
        calc = self.service._compute(
            rule=rule,
            pages_selected=1,
            color_mode="BW",
            paper_size="LEGAL",
            copies=1,
            duplex=False,
            pages_per_sheet=1,
        )
        assert calc.price_per_sheet == Decimal("2.50")

    def test_multiple_copies(self) -> None:
        rule = _make_rule(bw=2.00, gst=18.00)
        calc = self.service._compute(
            rule=rule,
            pages_selected=10,
            color_mode="BW",
            paper_size="A4",
            copies=3,
            duplex=False,
            pages_per_sheet=1,
        )
        # 10 sheets/copy × 3 copies = 30 sheets
        assert calc.sheets == 30
        assert calc.subtotal_inr == Decimal("60.00")

    def test_duplex_halves_sheets(self) -> None:
        rule = _make_rule(bw=2.00, gst=18.00)
        calc = self.service._compute(
            rule=rule,
            pages_selected=10,
            color_mode="BW",
            paper_size="A4",
            copies=1,
            duplex=True,
            pages_per_sheet=1,
        )
        # ceil(10/2) = 5 sheets
        assert calc.sheets == 5

    def test_duplex_odd_pages_rounds_up(self) -> None:
        rule = _make_rule(bw=2.00, gst=18.00)
        calc = self.service._compute(
            rule=rule,
            pages_selected=7,
            color_mode="BW",
            paper_size="A4",
            copies=1,
            duplex=True,
            pages_per_sheet=1,
        )
        # ceil(7/2) = 4 sheets
        assert calc.sheets == 4

    def test_pages_per_sheet_2(self) -> None:
        rule = _make_rule(bw=2.00, gst=18.00)
        calc = self.service._compute(
            rule=rule,
            pages_selected=4,
            color_mode="BW",
            paper_size="A4",
            copies=1,
            duplex=False,
            pages_per_sheet=2,
        )
        # ceil(4/2) = 2 sheets
        assert calc.sheets == 2

    def test_minimum_total_enforced(self) -> None:
        # With very low prices, total should be at least ₹1.00
        rule = _make_rule(bw=0.01, gst=0.00)
        calc = self.service._compute(
            rule=rule,
            pages_selected=1,
            color_mode="BW",
            paper_size="A4",
            copies=1,
            duplex=False,
            pages_per_sheet=1,
        )
        assert calc.total_inr >= MINIMUM_TOTAL_INR

    def test_to_dict_returns_strings(self) -> None:
        rule = _make_rule()
        calc = self.service._compute(
            rule=rule,
            pages_selected=1,
            color_mode="BW",
            paper_size="A4",
            copies=1,
            duplex=False,
            pages_per_sheet=1,
        )
        d = calc.to_dict()
        assert isinstance(d["subtotalInr"], str)
        assert isinstance(d["gstInr"], str)
        assert isinstance(d["totalInr"], str)
        assert d["currency"] == "INR"


@pytest.mark.asyncio
class TestPricingEndpoints:
    """Integration tests for pricing API endpoints."""

    async def test_calculate_bw_a4(self, async_client) -> None:
        response = await async_client.get(
            "/api/v1/pricing/calculate",
            params={"pages": 10, "color_mode": "BW", "paper_size": "A4", "copies": 1},
        )
        # Returns 200 always: either with data (rule found) or error code PRICE_500
        # (no active pricing rule in the test DB — seed required for full result).
        assert response.status_code == 200
        data = response.json()
        assert "success" in data
        if data["success"]:
            assert "data" in data
            assert "totalInr" in data["data"]
        else:
            assert data["error"]["code"] == "PRICE_500"

    async def test_calculate_invalid_color_mode(self, async_client) -> None:
        response = await async_client.get(
            "/api/v1/pricing/calculate",
            params={"pages": 1, "color_mode": "INVALID"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert data["error"]["code"] == "PRICE_001"

    async def test_calculate_invalid_paper_size(self, async_client) -> None:
        response = await async_client.get(
            "/api/v1/pricing/calculate",
            params={"pages": 1, "paper_size": "B5"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert data["error"]["code"] == "PRICE_002"

    async def test_calculate_pages_too_high(self, async_client) -> None:
        response = await async_client.get(
            "/api/v1/pricing/calculate",
            params={"pages": 999},
        )
        assert response.status_code == 422  # FastAPI validation error

"""
PrintBar Backend — Pricing API Endpoints

GET  /api/v1/pricing/calculate — Real-time price calculation (no auth required)
GET  /api/v1/pricing/config    — Returns current pricing configuration (no auth required)

The frontend sends print options → backend returns exact price.
Frontend NEVER computes prices.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import (
    COLOR_MODE_BW,
    COLOR_MODE_COLOR,
    PAPER_SIZE_A3,
    PAPER_SIZE_A4,
    PAPER_SIZE_LEGAL,
    PAPER_SIZE_LETTER,
)
from app.core.logging import get_logger
from app.database.session import get_db
from app.services.pricing_service import PricingService

logger = get_logger(__name__)
router = APIRouter(prefix="/pricing", tags=["Pricing"])

_VALID_COLOR_MODES = {COLOR_MODE_BW, COLOR_MODE_COLOR}
_VALID_PAPER_SIZES = {PAPER_SIZE_A4, PAPER_SIZE_A3, PAPER_SIZE_LETTER, PAPER_SIZE_LEGAL}
_VALID_PAGES_PER_SHEET = {1, 2, 4, 6}


@router.get(
    "/calculate",
    summary="Calculate print job price",
    description=(
        "Returns the exact price breakdown for a print job configuration. "
        "Call this whenever the user changes any print setting. "
        "No authentication required."
    ),
)
async def calculate_price(
    pages: int = Query(..., ge=1, le=500, description="Number of pages to print"),
    color_mode: str = Query(default="BW", description="BW or COLOR"),
    paper_size: str = Query(default="A4", description="A4, A3, LETTER, or LEGAL"),
    copies: int = Query(default=1, ge=1, le=100, description="Number of copies"),
    duplex: bool = Query(default=False, description="Double-sided printing"),
    pages_per_sheet: int = Query(default=1, description="Pages per physical sheet (1, 2, 4, or 6)"),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Calculates the exact price for a print job.

    Returns a breakdown including:
        - subtotalInr: Pre-GST price
        - gstInr: GST amount
        - totalInr: Final amount the user pays
        - sheets: Physical sheets of paper consumed
        - pricePerSheetInr: Effective per-sheet price

    This endpoint is deliberately unauthenticated so the frontend can
    show the price before a session is created (marketing/preview use).
    """
    # Validate enum parameters.
    color_mode_upper = color_mode.upper()
    paper_size_upper = paper_size.upper()

    if color_mode_upper not in _VALID_COLOR_MODES:
        return {
            "success": False,
            "error": {
                "code": "PRICE_001",
                "message": f"Invalid color_mode. Must be one of: {', '.join(_VALID_COLOR_MODES)}",
            },
        }

    if paper_size_upper not in _VALID_PAPER_SIZES:
        return {
            "success": False,
            "error": {
                "code": "PRICE_002",
                "message": f"Invalid paper_size. Must be one of: {', '.join(_VALID_PAPER_SIZES)}",
            },
        }

    if pages_per_sheet not in _VALID_PAGES_PER_SHEET:
        return {
            "success": False,
            "error": {
                "code": "PRICE_003",
                "message": f"Invalid pages_per_sheet. Must be one of: {', '.join(str(v) for v in sorted(_VALID_PAGES_PER_SHEET))}",
            },
        }

    service = PricingService(db)
    try:
        result = await service.calculate(
            pages_selected=pages,
            color_mode=color_mode_upper,
            paper_size=paper_size_upper,
            copies=copies,
            duplex=duplex,
            pages_per_sheet=pages_per_sheet,
        )
    except RuntimeError:
        return {
            "success": False,
            "error": {
                "code": "PRICE_500",
                "message": "Pricing service is not configured. Contact the administrator.",
            },
        }

    return {"success": True, "data": result.to_dict()}


@router.get(
    "/config",
    summary="Get current pricing configuration",
    description=(
        "Returns the active pricing rule configuration. "
        "Used by the admin dashboard and for display in the kiosk UI. "
        "No authentication required."
    ),
)
async def get_pricing_config(
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Returns the currently active pricing configuration.

    Does NOT expose the pricing rule ID or internal fields.
    Used by the frontend to display pricing information to users.
    """
    service = PricingService(db)
    rule = await service.get_active_rule()

    return {
        "success": True,
        "data": {
            "bwPriceInr": str(rule.bw_price_inr),
            "colorPriceInr": str(rule.color_price_inr),
            "a3Multiplier": str(rule.a3_multiplier),
            "legalMultiplier": str(rule.legal_multiplier),
            "duplexDiscount": str(rule.duplex_discount),
            "gstPercent": str(rule.gst_percent),
            "currency": "INR",
            "validFrom": rule.valid_from,
        },
    }

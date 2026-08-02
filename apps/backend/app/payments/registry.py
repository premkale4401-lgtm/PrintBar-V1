"""
PrintBar Backend — Payment Provider Registry

Single point of truth for the active payment provider.
Business logic imports get_active_provider() — never a specific gateway class.

To switch payment providers:
    1. Implement the PaymentProvider protocol in a new file under app/payments/.
    2. Change PAYMENT_PROVIDER setting in .env (or add logic here).
    3. No frontend changes required.
    4. No business logic changes required.
"""

from __future__ import annotations

from functools import lru_cache

from app.core.logging import get_logger
from app.payments.base import PaymentProvider

logger = get_logger(__name__)


@lru_cache(maxsize=1)
def get_active_provider() -> PaymentProvider:
    """
    Returns the singleton active payment provider.

    Currently hardwired to Razorpay. To support runtime-switchable providers,
    read from settings.PAYMENT_PROVIDER and instantiate accordingly.

    The lru_cache ensures only one instance per process lifetime.
    Call get_active_provider.cache_clear() in tests to reset.

    Returns:
        PaymentProvider — the active gateway adapter.
    """
    from app.payments.razorpay import razorpay_provider

    logger.info(
        "payment_provider_active",
        provider="RAZORPAY",
    )
    return razorpay_provider  # type: ignore[return-value]

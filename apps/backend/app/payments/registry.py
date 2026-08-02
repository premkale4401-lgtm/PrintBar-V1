"""
PrintBar Backend — Payment Provider Registry

Single point of truth for the active payment provider.
Business logic imports get_active_provider() — never a specific gateway class.

To switch payment providers:
    1. Set PAYMENT_PROVIDER=<provider> in .env (mock | razorpay | easebuzz).
    2. Implement the PaymentProvider protocol in a new file under app/payments/ if needed.
    3. Register it below.
    4. No frontend changes required.
    5. No business logic changes required.
"""

from __future__ import annotations

from functools import lru_cache

from app.core.logging import get_logger
from app.payments.base import PaymentProvider

logger = get_logger(__name__)


@lru_cache(maxsize=1)
def get_active_provider() -> PaymentProvider:
    """
    Returns the singleton active payment provider based on PAYMENT_PROVIDER setting.

    Supported providers:
        mock     — MockPaymentProvider (no credentials required, dev/CI only)
        razorpay — RazorpayProvider (requires RAZORPAY_KEY_ID + RAZORPAY_KEY_SECRET)
        easebuzz — EasebuzzProvider (legacy, requires EASEBUZZ_KEY + EASEBUZZ_SALT)

    The lru_cache ensures only one instance per process lifetime.
    Call get_active_provider.cache_clear() in tests to reset between test cases.

    Returns:
        PaymentProvider — the active gateway adapter.

    Raises:
        ValueError: If PAYMENT_PROVIDER is set to an unsupported value.
    """
    from app.core.config import get_settings
    settings = get_settings()

    # Validate credentials for real providers.
    settings.validate_payment_provider_credentials()

    provider_name = settings.PAYMENT_PROVIDER

    if provider_name == "mock":
        from app.payments.mock import mock_provider
        logger.info("payment_provider_active", provider="MOCK")
        return mock_provider  # type: ignore[return-value]

    if provider_name == "razorpay":
        from app.payments.razorpay import razorpay_provider
        logger.info("payment_provider_active", provider="RAZORPAY")
        return razorpay_provider  # type: ignore[return-value]

    if provider_name == "easebuzz":
        from app.payments.easebuzz import easebuzz_provider
        logger.info("payment_provider_active", provider="EASEBUZZ")
        return easebuzz_provider  # type: ignore[return-value]

    raise ValueError(
        f"Unsupported PAYMENT_PROVIDER: '{provider_name}'. "
        "Supported values: mock, razorpay, easebuzz"
    )

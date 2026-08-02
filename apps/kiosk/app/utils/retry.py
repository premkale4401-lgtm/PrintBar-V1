"""
PrintBar Kiosk Agent — Retry Utility

Exponential backoff helper for network operations.
"""
from __future__ import annotations
import asyncio
import logging
from typing import Callable, TypeVar

logger = logging.getLogger(__name__)
T = TypeVar("T")


async def retry_with_backoff(
    fn: Callable,
    *,
    max_attempts: int = 5,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    label: str = "operation",
) -> any:
    """
    Retries an async function with exponential backoff.

    Args:
        fn:           Async callable to retry.
        max_attempts: Maximum number of attempts before raising.
        base_delay:   Initial delay in seconds.
        max_delay:    Maximum delay cap.
        label:        Human-readable label for log messages.

    Returns:
        The return value of fn() on success.

    Raises:
        The last exception from fn() if all attempts fail.
    """
    delay = base_delay
    last_exc: Exception | None = None

    for attempt in range(1, max_attempts + 1):
        try:
            return await fn()
        except Exception as exc:
            last_exc = exc
            if attempt == max_attempts:
                break
            logger.warning(f"{label} failed (attempt {attempt}/{max_attempts}): {exc}. Retrying in {delay:.1f}s")
            await asyncio.sleep(delay)
            delay = min(delay * 2, max_delay)

    raise last_exc

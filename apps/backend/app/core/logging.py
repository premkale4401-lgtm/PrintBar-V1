"""
PrintBar Backend — Structured JSON Logging

Configures structlog for structured JSON logging across the entire backend.
Every log entry includes timestamp, level, module, request_id, and correlation_id.

Usage:
    from app.core.logging import get_logger
    logger = get_logger(__name__)
    logger.info("payment_verified", payment_id=str(payment_id), amount=amount)
"""

import logging
import sys
from typing import Any

import structlog
from structlog.types import EventDict, WrappedLogger

from app.core.config import get_settings


def _add_app_context(
    logger: WrappedLogger,
    method_name: str,
    event_dict: EventDict,
) -> EventDict:
    """
    Adds application-level metadata to every log entry.

    Injects app_name and environment so that logs from multiple
    services can be distinguished in centralized logging systems.
    """
    settings = get_settings()
    event_dict["app"] = settings.APP_NAME
    event_dict["env"] = settings.ENVIRONMENT
    return event_dict


def _drop_color_message_key(
    logger: WrappedLogger,
    method_name: str,
    event_dict: EventDict,
) -> EventDict:
    """
    Removes the color_message key added by uvicorn in some environments
    to keep log output clean and machine-parseable.
    """
    event_dict.pop("color_message", None)
    return event_dict


def configure_logging() -> None:
    """
    Configures structlog and the standard Python logging system.

    Call this exactly once at application startup in main.py.

    Log format:
        - JSON in production and staging.
        - Human-readable console in development.

    Every log record includes:
        - timestamp (ISO 8601 UTC)
        - level
        - logger (module name)
        - event
        - request_id (when set via context variable)
        - correlation_id (when set)
        - kiosk_id (when set)
        - session_id (when set)
    """
    settings = get_settings()

    # Shared processors run before rendering.
    shared_processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        _add_app_context,
        _drop_color_message_key,
        structlog.processors.StackInfoRenderer(),
    ]

    if settings.is_production or settings.ENVIRONMENT == "staging":
        # JSON output for machine-parseable logs in all non-dev environments.
        renderer = structlog.processors.JSONRenderer()
    else:
        # Pretty console output for development.
        renderer = structlog.dev.ConsoleRenderer(colors=True)

    structlog.configure(
        processors=shared_processors
        + [
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    if root_logger.handlers:
        root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(logging.DEBUG if settings.DEBUG else logging.INFO)

    # Quieten noisy third-party loggers.
    for noisy_logger in ("uvicorn.error", "uvicorn.access", "sqlalchemy.engine"):
        logging.getLogger(noisy_logger).handlers = []
        logging.getLogger(noisy_logger).propagate = True

    if not settings.is_production:
        logging.getLogger("sqlalchemy.engine").setLevel(
            logging.INFO if settings.DATABASE_ECHO else logging.WARNING
        )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """
    Returns a structlog bound logger for the given module name.

    Args:
        name: Typically __name__ from the calling module.

    Returns:
        A bound structlog logger with the module name attached.
    """
    return structlog.get_logger(name)  # type: ignore[return-value]

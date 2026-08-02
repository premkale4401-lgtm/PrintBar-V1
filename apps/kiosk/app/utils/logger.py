"""
PrintBar Kiosk Agent — Logger Setup

Configures structured logging with file rotation.
"""
from __future__ import annotations
import logging
import logging.handlers
import os


def setup_logger(log_dir: str, max_bytes: int = 10_485_760, backup_count: int = 10) -> None:
    """Configures the root logger with rotating file + console handlers."""
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, "kiosk.log")

    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s — %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )

    file_handler = logging.handlers.RotatingFileHandler(
        log_file, maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8"
    )
    file_handler.setFormatter(fmt)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(fmt)

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(file_handler)
    root.addHandler(console_handler)

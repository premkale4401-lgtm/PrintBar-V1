"""
PrintBar Kiosk Agent — Entry Point

Usage:
    python -m app

Starts the kiosk agent:
1. Loads configuration from kiosk.yaml and environment variables.
2. Authenticates with the backend.
3. Connects to the WebSocket.
4. Starts heartbeat sender.
5. Listens for print jobs and processes them.
"""
from __future__ import annotations
import asyncio
import logging
import sys
from app.config.loader import load_config
from app.utils.logger import setup_logger
from app.client.main import KioskClient


async def _main() -> None:
    settings = load_config()
    setup_logger(log_dir=settings.log_dir, max_bytes=settings.log_max_bytes, backup_count=settings.log_backup_count)
    logger = logging.getLogger(__name__)

    if not settings.kiosk_id or not settings.api_key:
        logger.error("Missing KIOSK_ID or KIOSK_API_KEY. Configure kiosk.yaml or set environment variables.")
        sys.exit(1)

    logger.info("kiosk_agent_starting", kiosk_id=settings.kiosk_id, name=settings.name)
    client = KioskClient(settings)
    await client.run()


if __name__ == "__main__":
    asyncio.run(_main())

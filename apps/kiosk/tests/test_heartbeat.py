"""
Tests for kiosk agent heartbeat sender.
"""

from __future__ import annotations
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))


def make_settings():
    from app.config.settings import KioskSettings

    return KioskSettings(
        kiosk_id="test-kiosk-uuid",
        api_key="test-key",
        heartbeat_interval_sec=1,
    )


@pytest.mark.asyncio
async def test_heartbeat_sends_correct_type():
    """HeartbeatSender sends messages with type=HEARTBEAT."""
    from app.heartbeat.sender import HeartbeatSender

    sent_messages = []

    async def mock_send(msg):
        sent_messages.append(msg)

    settings = make_settings()
    sender = HeartbeatSender(settings=settings, ws_send=mock_send)

    with patch(
        "app.monitoring.health.get_system_metrics",
        return_value={
            "cpu_percent": 5.0,
            "ram_percent": 40.0,
            "disk_percent": 20.0,
            "temperature_c": 45.0,
        },
    ):
        # Run one heartbeat iteration
        task = asyncio.create_task(sender.run_forever())
        await asyncio.sleep(1.2)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    assert len(sent_messages) >= 1
    assert sent_messages[0]["type"] == "HEARTBEAT"
    assert sent_messages[0]["data"]["kioskId"] == "test-kiosk-uuid"


@pytest.mark.asyncio
async def test_heartbeat_reflects_printing_flag():
    """HeartbeatSender includes the printing flag in payload."""
    from app.heartbeat.sender import HeartbeatSender

    sent_messages = []

    async def mock_send(msg):
        sent_messages.append(msg)

    settings = make_settings()
    sender = HeartbeatSender(settings=settings, ws_send=mock_send)
    sender.set_printing(True)

    with patch("app.monitoring.health.get_system_metrics", return_value={}):
        task = asyncio.create_task(sender.run_forever())
        await asyncio.sleep(1.2)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    assert sent_messages[0]["data"]["printing"] is True

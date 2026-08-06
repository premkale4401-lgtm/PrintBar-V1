"""
PrintBar Kiosk Agent — System Health Monitor

Collects CPU, RAM, disk, and temperature metrics.
"""

from __future__ import annotations
import logging

logger = logging.getLogger(__name__)


def get_system_metrics() -> dict:
    """
    Collects current system health metrics.

    Returns:
        Dict with cpu_percent, ram_percent, disk_percent, temperature_c.
    """
    try:
        import psutil

        cpu = psutil.cpu_percent(interval=0.5)
        ram = psutil.virtual_memory().percent
        disk = psutil.disk_usage("/").percent

        temp: float | None = None
        try:
            temps = psutil.sensors_temperatures()
            if temps:
                for key in ("cpu_thermal", "coretemp", "cpu-thermal"):
                    if key in temps and temps[key]:
                        temp = temps[key][0].current
                        break
        except Exception:
            pass

        return {
            "cpu_percent": cpu,
            "ram_percent": ram,
            "disk_percent": disk,
            "temperature_c": temp,
        }

    except ImportError:
        logger.warning("psutil not available — returning mock metrics")
        return {
            "cpu_percent": 0.0,
            "ram_percent": 0.0,
            "disk_percent": 0.0,
            "temperature_c": None,
        }

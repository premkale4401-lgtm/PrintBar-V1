"""
PrintBar Kiosk Agent — Configuration Loader

Loads configuration from kiosk.yaml and environment variables.
Environment variables override YAML values.
"""
from __future__ import annotations
import os
import yaml
from app.config.settings import KioskSettings


def load_config(config_path: str = "config/kiosk.yaml") -> KioskSettings:
    """
    Loads configuration from a YAML file and environment overrides.

    Args:
        config_path: Path to the kiosk.yaml config file.

    Returns:
        KioskSettings with all values populated.
    """
    data: dict = {}
    if os.path.exists(config_path):
        with open(config_path, "r") as f:
            data = yaml.safe_load(f) or {}

    settings = KioskSettings(
        kiosk_id=os.getenv("KIOSK_ID", data.get("kiosk_id", "")),
        api_key=os.getenv("KIOSK_API_KEY", data.get("api_key", "")),
        name=os.getenv("KIOSK_NAME", data.get("name", "PrintBar Kiosk")),
        backend_url=os.getenv("BACKEND_URL", data.get("backend_url", "http://localhost:8000")),
        cups_printer_name=os.getenv("CUPS_PRINTER", data.get("cups_printer_name", "")),
        heartbeat_interval_sec=int(os.getenv("HEARTBEAT_INTERVAL", data.get("heartbeat_interval_sec", 30))),
        temp_dir=os.getenv("TEMP_DIR", data.get("temp_dir", "/tmp/printbar")),
        log_dir=os.getenv("LOG_DIR", data.get("log_dir", "/var/log/printbar")),
    )
    return settings

"""Kiosk agent configuration dataclass."""
from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class KioskSettings:
    """All configuration for the PrintBar kiosk agent."""
    # Identity
    kiosk_id: str = ""
    api_key: str = ""
    name: str = "PrintBar Kiosk"

    # Backend connection
    backend_url: str = "http://localhost:8000"
    ws_url: str = ""  # Derived from backend_url if empty

    # Printer
    cups_printer_name: str = ""
    printer_options: dict = field(default_factory=dict)

    # Behaviour
    heartbeat_interval_sec: int = 30
    job_poll_interval_sec: int = 5
    max_ws_reconnect_delay_sec: int = 60
    download_timeout_sec: int = 120
    print_timeout_sec: int = 300

    # Storage
    temp_dir: str = "/tmp/printbar"
    log_dir: str = "/var/log/printbar"
    log_max_bytes: int = 10_485_760  # 10 MB
    log_backup_count: int = 10

    def __post_init__(self) -> None:
        if not self.ws_url:
            base = self.backend_url.replace("https://", "wss://").replace("http://", "ws://")
            self.ws_url = f"{base}/ws/kiosk/{self.kiosk_id}"
        if self.api_key and "api_key=" not in self.ws_url:
            sep = "&" if "?" in self.ws_url else "?"
            self.ws_url = f"{self.ws_url}{sep}api_key={self.api_key}"

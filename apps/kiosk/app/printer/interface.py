"""PrintBar Kiosk Agent — Printer Interface Abstract Base."""

from __future__ import annotations
from abc import ABC, abstractmethod


class PrinterInterface(ABC):
    """Abstract base class for all printer adapters."""

    @abstractmethod
    def get_printer_status(self) -> str: ...

    @abstractmethod
    def submit_job(self, pdf_path: str, **options) -> int: ...

    @abstractmethod
    def wait_for_completion(self, job_id: int, timeout_sec: int) -> bool: ...

    @abstractmethod
    def cancel_job(self, job_id: int) -> None: ...

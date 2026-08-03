"""
PrintBar Kiosk Agent — CUPS Printer Adapter (Milestone 9)

Submits print jobs to CUPS and monitors their status.
Requires cups Python bindings: pip install pycups
"""
from __future__ import annotations
import logging
import os
import time
from typing import Any

logger = logging.getLogger(__name__)

CUPS_JOB_STATES = {
    3: "PENDING",
    4: "HELD",
    5: "PROCESSING",
    6: "STOPPED",
    7: "CANCELED",
    8: "ABORTED",
    9: "COMPLETED",
}


class CupsAdapter:
    """Interfaces with CUPS for print job submission and monitoring."""

    def __init__(self, printer_name: str) -> None:
        self._printer_name = printer_name
        self._conn: Any = None
        if not self._printer_name:
            try:
                conn = self._get_connection()
                default = conn.getDefault()
                if not default:
                    raise RuntimeError("No default printer configured in CUPS.")
                self._printer_name = default
                logger.info("using_default_printer", printer=self._printer_name)
            except Exception as exc:
                logger.error("failed_to_resolve_default_printer", error=str(exc))
                raise

    def _get_connection(self) -> Any:
        """Returns a CUPS connection, creating one if needed."""
        try:
            import cups
            return cups.Connection()
        except ImportError:
            raise RuntimeError("pycups is not installed. Run: pip install pycups")

    def get_printer_status(self) -> str:
        """Returns current printer status string strictly mapped to allowed ENUM."""
        try:
            conn = self._get_connection()
            printers = conn.getPrinters()
            if self._printer_name not in printers:
                return "UNKNOWN"
                
            state = printers[self._printer_name].get("printer-state", 0)
            state_reasons = printers[self._printer_name].get("printer-state-reasons", [])
            state_reasons_str = str(state_reasons)
            
            if "media-empty" in state_reasons_str:
                return "PAPER_OUT"
            if "media-jam" in state_reasons_str or "toner-empty" in state_reasons_str or "marker-supply-empty" in state_reasons_str:
                return "ERROR"
            if "paused" in state_reasons_str or "offline" in state_reasons_str or "not-connected" in state_reasons_str:
                return "OFFLINE"
                
            if state == 3:
                return "READY"
            elif state == 4:
                return "PRINTING"
            elif state == 5:
                return "STOPPED"
            return "OFFLINE"
        except Exception as exc:
            logger.error("cups_status_error", error=str(exc))
            return "UNKNOWN"

    def submit_job(
        self,
        pdf_path: str,
        *,
        copies: int = 1,
        color_mode: str = "BW",
        duplex: bool = False,
        paper_size: str = "A4",
        orientation: str = "portrait",
    ) -> int:
        """
        Submits a PDF file to CUPS for printing.

        Args:
            pdf_path:    Path to the PDF file.
            copies:      Number of copies.
            color_mode:  "BW" or "COLOR".
            duplex:      True for double-sided printing.
            paper_size:  Paper size string.
            orientation: "portrait" or "landscape".

        Returns:
            CUPS job ID.
        """
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"PDF not found: {pdf_path}")

        conn = self._get_connection()

        options = {
            "copies": str(copies),
            "ColorModel": "Gray" if color_mode == "BW" else "RGB",
            "Duplex": "DuplexNoTumble" if duplex else "None",
            "PageSize": paper_size,
            "orientation-requested": "4" if orientation == "landscape" else "3",
            "fit-to-page": "True",
        }

        job_id = conn.printFile(self._printer_name, pdf_path, "PrintBar Job", options)
        logger.info("cups_job_submitted", job_id=job_id, printer=self._printer_name, copies=copies, color=color_mode)
        return job_id

    def wait_for_completion(self, job_id: int, timeout_sec: int = 300) -> bool:
        """
        Polls the job until it completes, fails, or times out.

        Returns:
            True if completed successfully, False otherwise.
        """
        conn = self._get_connection()
        deadline = time.monotonic() + timeout_sec

        while time.monotonic() < deadline:
            try:
                attrs = conn.getJobAttributes(job_id)
                state = attrs.get("job-state", 0)
                state_name = CUPS_JOB_STATES.get(state, "UNKNOWN")
                logger.debug("cups_job_state", job_id=job_id, state=state_name)

                if state == 9:  # COMPLETED
                    return True
                if state in (6, 7, 8):  # STOPPED, CANCELED, ABORTED
                    logger.error("cups_job_failed", job_id=job_id, state=state_name)
                    return False
                    
                # Also check printer hardware status
                printer_status = self.get_printer_status()
                if printer_status in ("PAPER_OUT", "ERROR", "OFFLINE"):
                    logger.error("cups_job_failed_hardware", job_id=job_id, printer_status=printer_status)
                    # Cancel the stuck job in CUPS so it doesn't block forever
                    self.cancel_job(job_id)
                    return False
                    
            except Exception as exc:
                logger.error("cups_poll_error", error=str(exc))
            time.sleep(3)

        logger.error("cups_job_timeout", job_id=job_id)
        return False

    def cancel_job(self, job_id: int) -> None:
        """Cancels a CUPS job."""
        try:
            conn = self._get_connection()
            conn.cancelJob(job_id)
            logger.info("cups_job_cancelled", job_id=job_id)
        except Exception as exc:
            logger.warning("cups_cancel_error", error=str(exc))

    def list_printers(self) -> list[str]:
        """Returns a list of all available CUPS printer names."""
        conn = self._get_connection()
        return list(conn.getPrinters().keys())

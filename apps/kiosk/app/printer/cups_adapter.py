"""
PrintBar Kiosk Agent — CUPS Printer Adapter

Submits print jobs to CUPS and monitors their status.
Requires cups Python bindings: pip install pycups

Performance: The CUPS connection is cached and reused across calls.
A new connection is only created if the existing one becomes stale.
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

# CUPS poll interval (seconds). Lower = faster completion detection.
_CUPS_POLL_INTERVAL_SEC = 2


class CupsAdapter:
    """Interfaces with CUPS for print job submission and monitoring.

    The CUPS connection is created once and reused — this avoids the
    overhead of creating a new Unix socket on every status poll.
    """

    def __init__(self, printer_name: str) -> None:
        self._printer_name = printer_name
        self._conn: Any = None          # Cached CUPS connection
        self._conn_stale: bool = True   # Force reconnect on first use

        if not self._printer_name:
            try:
                conn = self._get_connection()
                if conn is not None:
                    default = conn.getDefault()
                    if default:
                        self._printer_name = default
                        logger.info("using_default_printer", printer=self._printer_name)
            except Exception as exc:
                logger.error("failed_to_resolve_default_printer", error=str(exc))

    def _get_connection(self) -> Any:
        """Returns the cached CUPS connection, reconnecting if necessary.

        Connection is re-established only when:
        - First call (no connection yet)
        - Previous call failed (connection marked stale)
        """
        if not self._conn_stale and self._conn is not None:
            return self._conn

        try:
            import cups
            self._conn = cups.Connection()
            self._conn_stale = False
            logger.debug("cups_connection_created")
            return self._conn
        except ImportError:
            # pycups not installed — fall back to subprocess lp/lpstat.
            logger.warning("pycups_not_available_using_subprocess_fallback")
            self._conn = None
            self._conn_stale = False
            return None
        except Exception as exc:
            logger.error("cups_connection_failed", error=str(exc))
            self._conn = None
            self._conn_stale = True
            return None

    def _invalidate_connection(self) -> None:
        """Marks the cached connection as stale so next call reconnects."""
        self._conn_stale = True
        self._conn = None

    def get_printer_status(self) -> str:
        """Returns current printer status string mapped to allowed ENUM values."""
        try:
            conn = self._get_connection()
            if conn is not None:
                try:
                    printers = conn.getPrinters()
                except Exception:
                    self._invalidate_connection()
                    return "UNKNOWN"

                if self._printer_name not in printers:
                    return "OFFLINE"

                state = printers[self._printer_name].get("printer-state", 0)
                state_reasons = printers[self._printer_name].get("printer-state-reasons", [])
                state_reasons_str = str(state_reasons)

                if "media-empty" in state_reasons_str:
                    return "OUT_OF_PAPER"
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
            else:
                # Subprocess fallback (no pycups).
                import subprocess
                import shutil
                if shutil.which("lpstat"):
                    res = subprocess.run(
                        ["lpstat", "-p", self._printer_name or "PrintBar"],
                        capture_output=True, text=True, timeout=5,
                    )
                    output = res.stdout.lower()
                    if "disabled" in output or "off" in output:
                        return "OFFLINE"
                    if "printing" in output:
                        return "PRINTING"
                    if "idle" in output or "ready" in output:
                        return "READY"
                return "READY"
        except Exception as exc:
            logger.error("cups_status_error", error=str(exc))
            self._invalidate_connection()
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

        Returns the CUPS job ID (integer).
        """
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"PDF not found: {pdf_path}")

        conn = self._get_connection()
        if conn is not None:
            options = {
                "copies": str(copies),
                "ColorModel": "Gray" if color_mode.upper() == "BW" else "RGB",
                "print-color-mode": "monochrome" if color_mode.upper() == "BW" else "color",
                "Duplex": "DuplexNoTumble" if duplex else "None",
                "sides": "two-sided-long-edge" if duplex else "one-sided",
                "PageSize": paper_size,
                "media": paper_size,
                "orientation-requested": "4" if orientation.lower() == "landscape" else "3",
                "fit-to-page": "True",
            }
            try:
                job_id = conn.printFile(self._printer_name, pdf_path, "PrintBar Job", options)
                logger.info(
                    "cups_job_submitted",
                    job_id=job_id,
                    printer=self._printer_name,
                    copies=copies,
                    color=color_mode,
                    duplex=duplex,
                    paper=paper_size,
                )
                return job_id
            except Exception as exc:
                logger.error("cups_submit_error", error=str(exc))
                self._invalidate_connection()
                raise
        else:
            # Subprocess fallback (no pycups).
            import subprocess
            import shutil
            if shutil.which("lp"):
                cmd = ["lp", "-d", self._printer_name or "PrintBar", "-n", str(copies)]
                if color_mode.upper() == "BW":
                    cmd.extend(["-o", "ColorModel=Gray", "-o", "print-color-mode=monochrome"])
                else:
                    cmd.extend(["-o", "ColorModel=RGB", "-o", "print-color-mode=color"])
                if duplex:
                    cmd.extend(["-o", "sides=two-sided-long-edge", "-o", "Duplex=DuplexNoTumble"])
                else:
                    cmd.extend(["-o", "sides=one-sided", "-o", "Duplex=None"])
                cmd.extend(["-o", f"media={paper_size}", "-o", "fit-to-page=true"])
                if orientation.lower() == "landscape":
                    cmd.extend(["-o", "orientation-requested=4"])
                cmd.append(pdf_path)
                res = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
                logger.info("lp_cmd_submitted", stdout=res.stdout.strip(), stderr=res.stderr.strip())
                if res.returncode != 0:
                    raise RuntimeError(f"lp command failed: {res.stderr.strip()}")
                # Parse job ID from lp output: "request id is PrintBar-42 (1 file(s))"
                try:
                    job_num = int(res.stdout.split("-")[-1].split()[0])
                    return job_num
                except Exception:
                    return 1
            raise RuntimeError(
                "Cannot submit print job: pycups not available and lp command not found. "
                "Install pycups (pip install pycups) or CUPS CLI tools."
            )

    def wait_for_completion(self, job_id: int, timeout_sec: int = 300) -> bool:
        """
        Polls CUPS until the job completes, fails, or times out.

        Uses the cached CUPS connection — no new socket per poll cycle.

        Args:
            job_id:      CUPS job ID returned by submit_job().
            timeout_sec: Maximum seconds to wait (default 5 minutes).

        Returns:
            True  — job printed successfully.
            False — job failed, was cancelled, or timed out.
        """
        conn = self._get_connection()
        if conn is None:
            # pycups not available — cannot monitor; assume success (subprocess path).
            logger.warning(
                "cups_wait_skipped_no_pycups",
                job_id=job_id,
                note="Cannot monitor job without pycups — assuming success.",
            )
            return True

        deadline = time.monotonic() + timeout_sec

        while time.monotonic() < deadline:
            try:
                attrs = conn.getJobAttributes(job_id)
                state = attrs.get("job-state", 0)
                state_name = CUPS_JOB_STATES.get(state, "UNKNOWN")
                logger.info("cups_job_state", job_id=job_id, state=state_name)

                if state == 9:  # COMPLETED
                    return True
                if state in (6, 7, 8):  # STOPPED, CANCELED, ABORTED
                    logger.error("cups_job_failed", job_id=job_id, state=state_name)
                    return False

                # Check printer hardware status on every poll.
                printer_status = self.get_printer_status()
                if printer_status in ("OUT_OF_PAPER", "ERROR", "OFFLINE"):
                    logger.error(
                        "cups_job_failed_hardware",
                        job_id=job_id,
                        printer_status=printer_status,
                    )
                    # Cancel the stuck job so it doesn't block forever.
                    self.cancel_job(job_id)
                    return False

            except Exception as exc:
                err_str = str(exc)
                if "IPP" in err_str or "not-found" in err_str.lower():
                    # Job was purged from CUPS queue — treat as completed.
                    logger.info("cups_job_purged_from_queue_treating_as_complete", job_id=job_id)
                    return True
                logger.error("cups_poll_error", job_id=job_id, error=err_str)
                # Reconnect on error to recover from stale connection.
                self._invalidate_connection()
                conn = self._get_connection()
                if conn is None:
                    return False

            time.sleep(_CUPS_POLL_INTERVAL_SEC)

        logger.error("cups_job_timeout", job_id=job_id, timeout_sec=timeout_sec)
        return False

    def cancel_job(self, job_id: int) -> None:
        """Cancels a CUPS job."""
        try:
            conn = self._get_connection()
            if conn is not None:
                conn.cancelJob(job_id)
                logger.info("cups_job_cancelled", job_id=job_id)
        except Exception as exc:
            logger.warning("cups_cancel_error", job_id=job_id, error=str(exc))
            self._invalidate_connection()

    def list_printers(self) -> list[str]:
        """Returns a list of all available CUPS printer names."""
        conn = self._get_connection()
        if conn is not None:
            try:
                return list(conn.getPrinters().keys())
            except Exception:
                self._invalidate_connection()
        return [self._printer_name] if self._printer_name else []

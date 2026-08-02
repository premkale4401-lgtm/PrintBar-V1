"""
Tests for kiosk agent CUPS printer adapter (mocked CUPS).
"""
from __future__ import annotations
import pytest
from unittest.mock import MagicMock, patch
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))


def test_get_printer_status_ready():
    """CupsAdapter returns READY when printer state is 3 with no error reasons."""
    from app.printer.cups_adapter import CupsAdapter

    mock_cups = MagicMock()
    mock_cups.getPrinters.return_value = {
        "TestPrinter": {"printer-state": 3, "printer-state-reasons": []}
    }

    adapter = CupsAdapter("TestPrinter")
    with patch.object(adapter, "_get_connection", return_value=mock_cups):
        status = adapter.get_printer_status()

    assert status == "READY"


def test_get_printer_status_out_of_paper():
    """CupsAdapter returns OUT_OF_PAPER when media-empty reason present."""
    from app.printer.cups_adapter import CupsAdapter

    mock_cups = MagicMock()
    mock_cups.getPrinters.return_value = {
        "TestPrinter": {"printer-state": 5, "printer-state-reasons": ["media-empty-warning"]}
    }

    adapter = CupsAdapter("TestPrinter")
    with patch.object(adapter, "_get_connection", return_value=mock_cups):
        status = adapter.get_printer_status()

    assert status == "OUT_OF_PAPER"


def test_get_printer_status_offline_when_not_found():
    """CupsAdapter returns OFFLINE when printer name not in CUPS."""
    from app.printer.cups_adapter import CupsAdapter

    mock_cups = MagicMock()
    mock_cups.getPrinters.return_value = {}

    adapter = CupsAdapter("MissingPrinter")
    with patch.object(adapter, "_get_connection", return_value=mock_cups):
        status = adapter.get_printer_status()

    assert status == "OFFLINE"


def test_submit_job_calls_cups(tmp_path):
    """CupsAdapter.submit_job calls CUPS printFile with correct args."""
    from app.printer.cups_adapter import CupsAdapter

    # Create a fake PDF file
    pdf_file = tmp_path / "test.pdf"
    pdf_file.write_bytes(b"%PDF fake")

    mock_cups = MagicMock()
    mock_cups.printFile.return_value = 42  # fake job ID

    adapter = CupsAdapter("TestPrinter")
    with patch.object(adapter, "_get_connection", return_value=mock_cups):
        job_id = adapter.submit_job(str(pdf_file), copies=2, color_mode="BW", duplex=False)

    assert job_id == 42
    mock_cups.printFile.assert_called_once()

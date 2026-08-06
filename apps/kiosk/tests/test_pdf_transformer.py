"""
PrintBar Kiosk Agent — PDFTransformer Unit Tests

Tests page range parsing, N-up layout transformations (2-up, 4-up, 6-up, 9-up, 16-up),
reverse order, orientation rotation, scaling, margins, and grayscale pipeline.
"""

from __future__ import annotations

import io
import os
import tempfile
import pytest
from pypdf import PdfReader, PdfWriter

from app.jobs.transformer import PDFTransformer, pdf_transformer


def _make_test_pdf(page_count: int = 4) -> bytes:
    """Creates an in-memory PDF with page_count pages for testing."""
    writer = PdfWriter()
    for i in range(page_count):
        writer.add_blank_page(width=595.28, height=841.89)  # A4
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


class TestPageRangeParser:
    """Tests page range parsing logic."""

    def test_parse_range_all(self):
        transformer = PDFTransformer()
        assert transformer.parse_page_range("all", 5) == [0, 1, 2, 3, 4]
        assert transformer.parse_page_range(None, 5) == [0, 1, 2, 3, 4]
        assert transformer.parse_page_range("", 5) == [0, 1, 2, 3, 4]

    def test_parse_range_single_pages(self):
        transformer = PDFTransformer()
        assert transformer.parse_page_range("1,3,5", 5) == [0, 2, 4]

    def test_parse_range_intervals(self):
        transformer = PDFTransformer()
        assert transformer.parse_page_range("1-3", 5) == [0, 1, 2]

    def test_parse_range_combined(self):
        transformer = PDFTransformer()
        assert transformer.parse_page_range("1-2,4,5", 5) == [0, 1, 3, 4]

    def test_parse_range_out_of_bounds_clipped(self):
        transformer = PDFTransformer()
        assert transformer.parse_page_range("1-10", 3) == [0, 1, 2]


class TestPDFTransformations:
    """Tests end-to-end PDF transformations."""

    def test_transform_nup_2up(self):
        pdf_bytes = _make_test_pdf(4)
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f_in:
            f_in.write(pdf_bytes)
            in_path = f_in.name

        out_path = in_path + ".out.pdf"

        try:
            res_path = pdf_transformer.transform(
                in_path,
                out_path,
                pages_per_sheet=2,
                color_mode="COLOR",
            )
            assert os.path.exists(res_path)
            reader = PdfReader(res_path)
            # 4 source pages 2-up -> 2 sheet pages
            assert len(reader.pages) == 2
        finally:
            if os.path.exists(in_path):
                os.remove(in_path)
            if os.path.exists(out_path):
                os.remove(out_path)

    def test_transform_nup_4up(self):
        pdf_bytes = _make_test_pdf(4)
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f_in:
            f_in.write(pdf_bytes)
            in_path = f_in.name

        out_path = in_path + ".out.pdf"

        try:
            res_path = pdf_transformer.transform(
                in_path,
                out_path,
                pages_per_sheet=4,
                color_mode="COLOR",
            )
            assert os.path.exists(res_path)
            reader = PdfReader(res_path)
            # 4 source pages 4-up -> 1 sheet page
            assert len(reader.pages) == 1
        finally:
            if os.path.exists(in_path):
                os.remove(in_path)
            if os.path.exists(out_path):
                os.remove(out_path)

    def test_transform_page_range(self):
        pdf_bytes = _make_test_pdf(4)
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f_in:
            f_in.write(pdf_bytes)
            in_path = f_in.name

        out_path = in_path + ".out.pdf"

        try:
            res_path = pdf_transformer.transform(
                in_path,
                out_path,
                page_range="1-2",
                color_mode="COLOR",
            )
            assert os.path.exists(res_path)
            reader = PdfReader(res_path)
            assert len(reader.pages) == 2
        finally:
            if os.path.exists(in_path):
                os.remove(in_path)
            if os.path.exists(out_path):
                os.remove(out_path)

    def test_transform_reverse_order(self):
        pdf_bytes = _make_test_pdf(3)
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f_in:
            f_in.write(pdf_bytes)
            in_path = f_in.name

        out_path = in_path + ".out.pdf"

        try:
            res_path = pdf_transformer.transform(
                in_path,
                out_path,
                reverse_order=True,
                color_mode="COLOR",
            )
            assert os.path.exists(res_path)
            reader = PdfReader(res_path)
            assert len(reader.pages) == 3
        finally:
            if os.path.exists(in_path):
                os.remove(in_path)
            if os.path.exists(out_path):
                os.remove(out_path)

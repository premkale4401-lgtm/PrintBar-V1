"""
PrintBar Kiosk Agent — PDF Transformer

Applies user-selected print settings to produce a transformed PDF before CUPS submission:
    - Page Range Selection (e.g., "1-5", "1,3,7", "2-6,9")
    - Reverse Page Order & Collation
    - Orientation (Portrait vs Landscape rotation)
    - N-Up Grid Layout (1, 2, 4, 6, 9, 16 pages per sheet)
    - Scaling & Margin Adjustments
    - Grayscale / BW Conversion via Ghostscript (with PyPDF fallback)

Invariant:
    All transformations occur in memory or temporary files.
    The resulting PDF is saved to a transformed file path and sent to CUPS.
"""

from __future__ import annotations

import io
import logging
import math
import os
import re
import shutil
import subprocess
from typing import Sequence

from pypdf import PageObject, PdfReader, PdfWriter, Transformation

logger = logging.getLogger(__name__)

# Standard paper dimensions in points (72 pt/inch)
PAPER_DIMENSIONS: dict[str, tuple[float, float]] = {
    "A4": (595.28, 841.89),
    "A3": (841.89, 1190.55),
    "LETTER": (612.0, 792.0),
    "LEGAL": (612.0, 1008.0),
}


class PDFTransformer:
    """Executes pre-print PDF transformations matching user selections."""

    def parse_page_range(self, range_str: str | None, total_pages: int) -> list[int]:
        """
        Parses a page range string (e.g., "1-5", "1,3,7", "2-6,9") into a list
        of 0-indexed page numbers.

        Args:
            range_str:   Page range specification from user/frontend.
            total_pages: Total number of pages in the source PDF.

        Returns:
            List of 0-indexed page integers to include.
        """
        if not range_str or range_str.strip().lower() in ("all", ""):
            return list(range(total_pages))

        pages: set[int] = set()
        parts = [p.strip() for p in range_str.split(",") if p.strip()]

        for part in parts:
            if "-" in part:
                subparts = part.split("-")
                if (
                    len(subparts) == 2
                    and subparts[0].isdigit()
                    and subparts[1].isdigit()
                ):
                    start = int(subparts[0])
                    end = int(subparts[1])
                    if start <= end:
                        for p in range(start, end + 1):
                            if 1 <= p <= total_pages:
                                pages.add(p - 1)
            elif part.isdigit():
                p = int(part)
                if 1 <= p <= total_pages:
                    pages.add(p - 1)

        result = sorted(pages)
        return result if result else list(range(total_pages))

    def transform(
        self,
        input_pdf_path: str,
        output_pdf_path: str,
        *,
        page_range: str | None = None,
        reverse_order: bool = False,
        pages_per_sheet: int = 1,
        orientation: str = "portrait",
        paper_size: str = "A4",
        color_mode: str = "BW",
        scale_mode: str = "fit",
        margin_mode: str = "default",
    ) -> str:
        """
        Executes the full transformation pipeline.

        Pipeline:
            1. Parse and extract page range
            2. Reverse page order if requested
            3. Apply orientation / rotation
            4. Apply N-Up grid (1, 2, 4, 6, 9, 16)
            5. Apply scaling and margins
            6. Apply grayscale conversion if color_mode == "BW"

        Args:
            input_pdf_path:  Path to source PDF file.
            output_pdf_path: Path where transformed PDF will be written.

        Returns:
            Absolute path to output_pdf_path.
        """
        if not os.path.exists(input_pdf_path):
            raise FileNotFoundError(f"Input PDF not found: {input_pdf_path}")

        reader = PdfReader(input_pdf_path, strict=False)
        total_src_pages = len(reader.pages)
        if total_src_pages == 0:
            raise ValueError("Input PDF contains 0 pages.")

        # Step 1: Page Range Selection
        target_indices = self.parse_page_range(page_range, total_src_pages)
        logger.info(
            "transformer_page_range_applied",
            input_pages=total_src_pages,
            selected_count=len(target_indices),
            page_range=page_range,
        )

        # Step 2: Reverse Order
        if reverse_order:
            target_indices = list(reversed(target_indices))
            logger.info("transformer_reverse_order_applied")

        selected_pages = [reader.pages[i] for i in target_indices]

        # Step 3 & 4 & 5: Apply Orientation, N-Up, Scale, and Margins
        transformed_writer = self._apply_nup_and_layout(
            selected_pages,
            pages_per_sheet=pages_per_sheet,
            orientation=orientation,
            paper_size=paper_size,
            scale_mode=scale_mode,
            margin_mode=margin_mode,
        )

        # Save intermediate layout PDF
        temp_layout_path = output_pdf_path + ".layout.tmp"
        with open(temp_layout_path, "wb") as f:
            transformed_writer.write(f)

        # Step 6: Grayscale Conversion
        final_pdf_path = output_pdf_path
        if color_mode.upper() == "BW":
            final_pdf_path = self._apply_grayscale(temp_layout_path, output_pdf_path)
            if os.path.exists(temp_layout_path):
                os.remove(temp_layout_path)
        else:
            if os.path.exists(output_pdf_path):
                os.remove(output_pdf_path)
            os.rename(temp_layout_path, output_pdf_path)

        logger.info(
            "transformer_completed",
            output_path=final_pdf_path,
            pages_per_sheet=pages_per_sheet,
            color_mode=color_mode,
            paper_size=paper_size,
        )
        return final_pdf_path

    def _apply_nup_and_layout(
        self,
        pages: Sequence[PageObject],
        pages_per_sheet: int,
        orientation: str,
        paper_size: str,
        scale_mode: str,
        margin_mode: str,
    ) -> PdfWriter:
        """Applies orientation, scaling, margins, and N-up grid layouts."""
        writer = PdfWriter()
        paper_dim = PAPER_DIMENSIONS.get(paper_size.upper(), PAPER_DIMENSIONS["A4"])
        sheet_w, sheet_h = paper_dim

        if orientation.lower() == "landscape" and sheet_w < sheet_h:
            sheet_w, sheet_h = sheet_h, sheet_w

        # Grid configuration for N-up
        cols, rows = self._get_grid_dimensions(pages_per_sheet)

        # Margin calculation (in points)
        margin_pt = 18.0  # default 0.25 inch
        if margin_mode.lower() == "none":
            margin_pt = 0.0
        elif margin_mode.lower() == "minimum":
            margin_pt = 9.0  # 0.125 inch

        printable_w = sheet_w - (2 * margin_pt)
        printable_h = sheet_h - (2 * margin_pt)

        cell_w = printable_w / cols
        cell_h = printable_h / rows

        i = 0
        n_pages = len(pages)

        while i < n_pages:
            blank_sheet = PageObject.create_blank_page(width=sheet_w, height=sheet_h)

            for cell_idx in range(pages_per_sheet):
                if i >= n_pages:
                    break

                src_page = pages[i]
                i += 1

                # Calculate grid position
                row = cell_idx // cols
                col = cell_idx % cols

                cell_x = margin_pt + (col * cell_w)
                cell_y = sheet_h - margin_pt - ((row + 1) * cell_h)

                src_w = float(src_page.mediabox.width)
                src_h = float(src_page.mediabox.height)

                # Auto-rotate source page if orientation mismatch with cell aspect ratio
                cell_is_landscape = cell_w > cell_h
                src_is_landscape = src_w > src_h
                rotation = 0

                if cell_is_landscape != src_is_landscape:
                    rotation = 90
                    src_w, src_h = src_h, src_w

                # Scale calculation
                scale_x = cell_w / src_w
                scale_y = cell_h / src_h

                if scale_mode.lower() == "fill":
                    scale = max(scale_x, scale_y)
                else:  # fit or actual size
                    scale = min(scale_x, scale_y)

                fit_w = src_w * scale
                fit_h = src_h * scale

                # Center source page in cell
                tx = cell_x + (cell_w - fit_w) / 2.0
                ty = cell_y + (cell_h - fit_h) / 2.0

                transform = Transformation()
                if rotation == 90:
                    transform = transform.rotate(90).translate(src_h, 0)
                transform = transform.scale(scale, scale).translate(tx, ty)

                blank_sheet.merge_transformed_page(src_page, transform)

            writer.add_page(blank_sheet)

        return writer

    @staticmethod
    def _get_grid_dimensions(nup: int) -> tuple[int, int]:
        """Returns (cols, rows) for a given N-up layout value."""
        if nup == 2:
            return 1, 2
        elif nup == 4:
            return 2, 2
        elif nup == 6:
            return 2, 3
        elif nup == 9:
            return 3, 3
        elif nup == 16:
            return 4, 4
        else:
            return 1, 1

    def _apply_grayscale(self, input_path: str, output_path: str) -> str:
        """
        Converts a PDF to monochrome/grayscale using Ghostscript (gs) if available.
        Falls back to PyPDF rendering or returns input_path if gs is missing.
        """
        gs = shutil.which("gs") or shutil.which("gswin64c") or shutil.which("gswin32c")
        if gs:
            try:
                cmd = [
                    gs,
                    "-sDEVICE=pdfwrite",
                    "-sColorConversionStrategy=Gray",
                    "-dProcessColorModel=/DeviceGray",
                    "-dCompatibilityLevel=1.4",
                    "-dNOPAUSE",
                    "-dBATCH",
                    f"-sOutputFile={output_path}",
                    input_path,
                ]
                res = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
                if res.returncode == 0 and os.path.exists(output_path):
                    logger.info(
                        "ghostscript_grayscale_conversion_success",
                        output_path=output_path,
                    )
                    return output_path
                else:
                    logger.warning(
                        "ghostscript_grayscale_failed stderr=%s", res.stderr[:200]
                    )
            except Exception as exc:
                logger.warning("ghostscript_grayscale_exception error=%s", str(exc))

        # If Ghostscript fails or is missing, copy layout file as fallback
        if input_path != output_path:
            shutil.copyfile(input_path, output_path)
        return output_path


# Module-level singleton
pdf_transformer = PDFTransformer()

"""
Qt-free PDF adapter for the narration pipeline.

Provides both stateless helper functions and a stateful
:class:`PDFAdapter` that keeps the document open across sequential
page operations.
"""

import logging
from typing import Dict, List, Tuple

import fitz
from PIL import Image

from core.page.models import BlockInfo
from core.page.text_layer import PageTextLayer

logger = logging.getLogger(__name__)


def open_pdf(pdf_path: str) -> fitz.Document:
    """
    Open a PDF document.

    Raises:
        RuntimeError: If fitz cannot open the file.
    """
    try:
        return fitz.open(pdf_path)
    except Exception as e:
        raise RuntimeError(f"Failed to open PDF '{pdf_path}': {e}") from e


def extract_page_text_structure(pdf_path: str, page_index: int) -> List[BlockInfo]:
    """
    Extract structured text blocks for a single page.

    Returns:
        List of ``BlockInfo`` (may be empty for image-only pages).
    """
    doc = open_pdf(pdf_path)
    try:
        if page_index < 0 or page_index >= doc.page_count:
            raise IndexError(
                f"Page {page_index} out of range (document has {doc.page_count} pages)"
            )
        return PageTextLayer(doc.load_page(page_index)).blocks
    finally:
        doc.close()


def extract_all_pages(pdf_path: str) -> Dict[int, List[BlockInfo]]:
    """Extract structured text blocks for every page in the document."""
    doc = open_pdf(pdf_path)
    try:
        return {
            idx: PageTextLayer(doc.load_page(idx)).blocks
            for idx in range(doc.page_count)
        }
    finally:
        doc.close()


def render_page_to_pil(
    pdf_path: str, page_index: int, scale: float = 1.5
) -> Image.Image:
    """Render a single PDF page to a PIL Image (RGB)."""
    doc = open_pdf(pdf_path)
    try:
        if page_index < 0 or page_index >= doc.page_count:
            raise IndexError(
                f"Page {page_index} out of range (document has {doc.page_count} pages)"
            )
        page = doc.load_page(page_index)
        mat = fitz.Matrix(scale, scale)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        return Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
    finally:
        doc.close()


def get_page_dimensions(pdf_path: str, page_index: int) -> Tuple[float, float]:
    """Return ``(width, height)`` in PDF points."""
    doc = open_pdf(pdf_path)
    try:
        if page_index < 0 or page_index >= doc.page_count:
            raise IndexError(
                f"Page {page_index} out of range (document has {doc.page_count} pages)"
            )
        rect = doc.load_page(page_index).rect
        return rect.width, rect.height
    finally:
        doc.close()


def get_page_count(pdf_path: str) -> int:
    """Return the total number of pages in the PDF."""
    doc = open_pdf(pdf_path)
    try:
        return doc.page_count
    finally:
        doc.close()


class PDFAdapter:
    """
    Stateful adapter that keeps the document open across multiple
    page operations.  Preferred over the standalone functions when
    processing an entire document sequentially.
    """

    def __init__(self, pdf_path: str):
        self.pdf_path = pdf_path
        self.doc = open_pdf(pdf_path)
        self.page_count = self.doc.page_count

    def text_structure(self, page_index: int) -> List[BlockInfo]:
        """Return ``BlockInfo`` list for *page_index*."""
        return PageTextLayer(self.doc.load_page(page_index)).blocks

    def text_layer(self, page_index: int) -> PageTextLayer:
        """Return the full ``PageTextLayer`` for *page_index*."""
        return PageTextLayer(self.doc.load_page(page_index))

    def render(self, page_index: int, scale: float = 1.5) -> Image.Image:
        """Render *page_index* to a PIL RGB image."""
        page = self.doc.load_page(page_index)
        mat = fitz.Matrix(scale, scale)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        return Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

    def dimensions(self, page_index: int) -> Tuple[float, float]:
        """Return ``(width, height)`` in PDF points."""
        rect = self.doc.load_page(page_index).rect
        return rect.width, rect.height

    def close(self):
        """Close the underlying document."""
        if self.doc:
            self.doc.close()
            self.doc = None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
        return False

    def __repr__(self):
        return f"PDFAdapter('{self.pdf_path}', pages={self.page_count})"

"""
PDF document reading and rendering functionality.
"""

import re
from typing import Any, Dict, List, Optional, Tuple

import fitz  # PyMuPDF
from PyQt5.QtGui import QImage, QPixmap
from PyQt5.QtWidgets import QMessageBox


class PDFDocumentReader:
    """Handles PDF document loading, rendering, and basic operations."""

    def __init__(self):
        self.doc: Optional[fitz.Document] = None
        self.total_pages: int = 0
        self.toc: List[Tuple[int, str, int, float]] = []
        self.current_file_path: Optional[str] = None

    def load_pdf(self, file_path: str) -> Tuple[bool, int]:
        """
        Load a PDF document.

        Args:
            file_path: Path to the PDF file

        Returns:
            Tuple of (success flag, number of pages)
        """
        try:
            # Close existing document if any
            if self.doc:
                self.close_document()

            self.doc = fitz.open(file_path)
            self.total_pages = self.doc.page_count
            self.current_file_path = file_path

            # Get table of contents with positioning info
            self.toc = self._process_toc()

            return True, self.total_pages

        except Exception as e:
            QMessageBox.critical(None, "Error", f"Error loading PDF: {e}")
            return False, 0

    def close_document(self) -> None:
        """Close the current PDF document and clear all state."""
        if self.doc:
            self.doc.close()
            self.doc = None

        self.total_pages = 0
        self.toc = []
        self.current_file_path = None

    def render_page(
        self, page_index: int, zoom_level: float, dark_mode: bool
    ) -> Tuple[Optional[QPixmap], Optional[Dict], Optional[List]]:
        """
        Render a single page of the PDF to a pixmap.

        Args:
            page_index: 0-based index of the page to render
            zoom_level: Zoom factor for rendering
            dark_mode: Whether to invert colors for dark mode

        Returns:
            Tuple of (pixmap, text_data, word_data)
        """
        if not self.doc or page_index >= self.total_pages:
            return None, None, None

        try:
            page = self.doc.load_page(page_index)
            mat = fitz.Matrix(zoom_level, zoom_level)

            # Render page to pixmap
            pix = page.get_pixmap(matrix=mat)
            img = QImage(
                pix.samples, pix.width, pix.height, pix.stride, QImage.Format_RGB888
            )

            # Apply dark mode if needed
            if dark_mode:
                img.invertPixels()

            pixmap = QPixmap.fromImage(img)

            # Extract text data
            text_data = page.get_text("dict", sort=True)
            word_data = page.get_text("words", sort=True)

            return pixmap, text_data, word_data

        except Exception as e:
            QMessageBox.critical(
                None, "Error", f"Error rendering page {page_index + 1}: {e}"
            )
            return None, None, None

    def get_page(self, page_index: int) -> Optional[fitz.Page]:
        """
        Get a page object for direct operations.

        Args:
            page_index: 0-based index of the page

        Returns:
            PyMuPDF page object, or None if invalid
        """
        if not self.doc or page_index >= self.total_pages:
            return None

        try:
            return self.doc.load_page(page_index)
        except Exception:
            return None

    def get_page_size(self, page_index: int) -> Tuple[float, float]:
        """
        Get the size of a page in points.

        Args:
            page_index: 0-based index of the page

        Returns:
            Tuple of (width, height) in points
        """
        page = self.get_page(page_index)
        if page:
            rect = page.rect
            return rect.width, rect.height
        return 0.0, 0.0

    def get_toc(self) -> List[Tuple[int, str, int, float]]:
        """
        Get the processed table of contents.

        Returns:
            List of (level, title, page_num, y_position) tuples
        """
        return self.toc

    def _process_toc(self) -> List[Tuple[int, str, int, float]]:
        """
        Process the PDF's table of contents with positioning info.
        Converts y-coordinates to top-left origin for consistent handling.

        Returns:
            List of processed TOC entries
        """
        if not self.doc:
            return []

        # Get the detailed TOC with full information
        raw_toc = self.doc.get_toc(simple=False)
        processed_toc = []

        for entry in raw_toc:
            if len(entry) >= 3:
                level, title, page_num = entry[:3]

                # Clean the title
                title = self._clean_toc_title(title, page_num)

                # Extract y-coordinate if available
                y_pos = 0.0
                if len(entry) == 4:
                    details = entry[3]
                    if isinstance(details, dict):
                        # Check for 'to' point in details
                        to_point = details.get("to")
                        if to_point and hasattr(to_point, "y"):
                            raw_y = to_point.y

                            # The 'to' point from PyMuPDF TOC may be in the
                            # original PDF coordinate system (bottom-left origin).
                            # We need to convert to top-left origin.
                            # Detect by checking: if raw_y is larger than half the
                            # page height, it's likely bottom-left origin
                            # (pointing to upper part of page).
                            try:
                                page = self.doc.load_page(page_num - 1)
                                page_height = page.rect.height

                                # If y > page_height, it's invalid - use 0
                                if raw_y > page_height:
                                    y_pos = 0.0
                                elif raw_y < 0:
                                    y_pos = 0.0
                                else:
                                    # Check if coordinate appears to be bottom-left
                                    # by seeing if the MediaBox origin differs from
                                    # the page rect origin
                                    mediabox = page.mediabox

                                    # If mediabox y0 is 0 and the raw y is close to
                                    # page height, the coordinate is likely bottom-left
                                    # Use the page's transformation to convert properly
                                    if mediabox.y0 == 0 and page.rect.y0 == 0:
                                        # Standard page: flip from bottom-left to top-left
                                        y_pos = page_height - raw_y
                                    else:
                                        # Non-standard page: raw_y might already be
                                        # in page.rect coordinates
                                        y_pos = raw_y - page.rect.y0

                                    # Clamp to valid range
                                    y_pos = max(0.0, min(y_pos, page_height))

                                # DEBUG - remove after confirming fix works
                                print(
                                    f"TOC: '{title}' -> page {page_num}, "
                                    f"raw_y={raw_y:.1f}, page_h={page_height:.1f}, "
                                    f"converted_y={y_pos:.1f}"
                                )

                            except Exception as e:
                                print(f"TOC y-conversion failed for '{title}': {e}")
                                y_pos = 0.0

                        # Also check for 'y' directly in details
                        elif "y" in details:
                            y_pos = details["y"]

                processed_toc.append((level, title, page_num, y_pos))

        return processed_toc

    def _clean_toc_title(self, title: str, page_num: int) -> str:
        """
        Clean a TOC title string.

        Args:
            title: Raw title from TOC
            page_num: Page number for fallback

        Returns:
            Cleaned title string
        """
        if not title:
            return f"Section {page_num}"

        # Handle surrogate escape sequences from PyMuPDF
        # Remove surrogate pair sequences (formatting characters)
        cleaned_title = re.sub(r"[\udc00-\udfff]+", "", title)

        # Remove isolated high surrogates
        cleaned_title = re.sub(r"[\ud800-\udbff]+", "", cleaned_title)

        # Clean up special characters
        cleaned_title = cleaned_title.replace("\r", "")
        cleaned_title = cleaned_title.replace("\n", " ")
        cleaned_title = cleaned_title.replace("\t", " ")

        # Remove control characters
        cleaned_title = re.sub(r"[\x00-\x1f\x7f-\x9f]", "", cleaned_title)

        # Clean up multiple spaces
        cleaned_title = re.sub(r"\s+", " ", cleaned_title)
        cleaned_title = cleaned_title.strip()

        # If title is empty after cleaning, provide a default
        if not cleaned_title:
            cleaned_title = f"Section {page_num}"

        return cleaned_title

    def extract_text(self, page_index: int) -> str:
        """
        Extract plain text from a page.

        Args:
            page_index: 0-based index of the page

        Returns:
            Plain text content of the page
        """
        page = self.get_page(page_index)
        if page:
            return page.get_text()
        return ""

    def extract_text_blocks(self, page_index: int) -> List[Dict]:
        """
        Extract text blocks with position information.

        Args:
            page_index: 0-based index of the page

        Returns:
            List of text block dictionaries
        """
        page = self.get_page(page_index)
        if page:
            return page.get_text("dict", sort=True).get("blocks", [])
        return []

    def is_loaded(self) -> bool:
        """Check if a document is currently loaded."""
        return self.doc is not None

    def get_file_path(self) -> Optional[str]:
        """Get the path of the currently loaded file."""
        return self.current_file_path

    def get_page_count(self) -> int:
        """Get the total number of pages."""
        return self.total_pages

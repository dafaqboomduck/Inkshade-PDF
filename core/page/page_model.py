"""
Unified page model combining rendering, text, and links.
"""

from typing import Dict, List, Optional, Tuple

import fitz
from PyQt5.QtGui import QImage, QPixmap

from .link_layer import PageLinkLayer
from .models import CharacterInfo, InteractionResult, InteractionType, LinkInfo
from .text_layer import PageTextLayer


class PageModel:
    """
    Complete model for a PDF page with all interactive elements.

    Provides unified access to:
    - Page rendering
    - Character-level text selection
    - Clickable links
    - Page metadata

    Uses lazy loading for text and link layers to optimize memory.
    """

    def __init__(self, doc: fitz.Document, page_index: int):
        self._doc = doc
        self.page_index = page_index
        self._page: Optional[fitz.Page] = None

        # Lazy-loaded layers
        self._text_layer: Optional[PageTextLayer] = None
        self._link_layer: Optional[PageLinkLayer] = None

        # Cached page info
        self._rect: Optional[fitz.Rect] = None
        self._rotation: int = 0

        # Rendering cache
        self._pixmap_cache: Dict[Tuple[float, bool], QPixmap] = {}
        self._max_cache_size = 3  # Keep last 3 zoom levels

    @property
    def page(self) -> fitz.Page:
        """Get the underlying fitz page, loading if necessary."""
        if self._page is None:
            self._page = self._doc.load_page(self.page_index)
            self._rect = self._page.rect
            self._rotation = self._page.rotation
        return self._page

    @property
    def rect(self) -> fitz.Rect:
        """Get page rectangle (dimensions)."""
        if self._rect is None:
            _ = self.page  # Load page to get rect
        return self._rect

    @property
    def width(self) -> float:
        """Page width in points."""
        return self.rect.width

    @property
    def height(self) -> float:
        """Page height in points."""
        return self.rect.height

    @property
    def rotation(self) -> int:
        """Page rotation in degrees."""
        if self._rotation is None:
            _ = self.page
        return self._rotation

    @property
    def text_layer(self) -> PageTextLayer:
        """Get text layer, creating if necessary."""
        if self._text_layer is None:
            try:
                self._text_layer = PageTextLayer(self.page)
            except Exception as e:
                # Return empty text layer on failure
                self._text_layer = PageTextLayer.__new__(PageTextLayer)
                self._text_layer.characters = []
                self._text_layer.blocks = []
                self._text_layer._char_grid = {}
        return self._text_layer

    @property
    def link_layer(self) -> PageLinkLayer:
        """Get link layer, creating if necessary."""
        if self._link_layer is None:
            try:
                self._link_layer = PageLinkLayer(self.page, self._doc)
            except Exception as e:
                self._link_layer = PageLinkLayer.__new__(PageLinkLayer)
                self._link_layer.links = []
        return self._link_layer

    def render_pixmap(
        self, zoom: float, dark_mode: bool = False, use_cache: bool = True
    ) -> QPixmap:
        """
        Render page to a QPixmap at the specified zoom level.

        Args:
            zoom: Zoom factor (1.0 = 100%)
            dark_mode: Whether to invert colors
            use_cache: Whether to use/store in cache

        Returns:
            QPixmap of the rendered page
        """
        cache_key = (zoom, dark_mode)

        # Check cache
        if use_cache and cache_key in self._pixmap_cache:
            return self._pixmap_cache[cache_key]

        # Render
        mat = fitz.Matrix(zoom, zoom)
        pix = self.page.get_pixmap(matrix=mat, alpha=False)

        # Convert to QImage
        img = QImage(
            pix.samples, pix.width, pix.height, pix.stride, QImage.Format_RGB888
        )

        # Apply dark mode
        if dark_mode:
            img.invertPixels()

        # Convert to QPixmap
        pixmap = QPixmap.fromImage(img)

        # Cache management
        if use_cache:
            self._pixmap_cache[cache_key] = pixmap

            # Limit cache size
            if len(self._pixmap_cache) > self._max_cache_size:
                # Remove oldest entry
                oldest_key = next(iter(self._pixmap_cache))
                del self._pixmap_cache[oldest_key]

        return pixmap

    def get_element_at_point(
        self, x: float, y: float, zoom: float = 1.0
    ) -> InteractionResult:
        """
        Determine what interactive element is at a screen point.

        Args:
            x: X coordinate in screen pixels
            y: Y coordinate in screen pixels
            zoom: Current zoom level

        Returns:
            InteractionResult with type and element
        """
        # Convert to PDF coordinates
        pdf_x = x / zoom
        pdf_y = y / zoom

        # Check links first (highest priority for clicking)
        link = self.link_layer.get_link_at_point(pdf_x, pdf_y)
        if link:
            return InteractionResult(type=InteractionType.LINK, element=link)

        # Check text
        char = self.text_layer.get_char_at_point(pdf_x, pdf_y)
        if char:
            return InteractionResult(type=InteractionType.TEXT, element=char)

        return InteractionResult(type=InteractionType.NONE)

    def get_nearest_text(
        self, x: float, y: float, zoom: float = 1.0, max_distance: float = 20.0
    ) -> Optional[CharacterInfo]:
        """
        Find the nearest text character to a point.

        Useful for starting selection near but not exactly on text.
        """
        pdf_x = x / zoom
        pdf_y = y / zoom
        return self.text_layer.get_nearest_char(pdf_x, pdf_y, max_distance / zoom)

    def get_text_in_rect(
        self, rect: Tuple[float, float, float, float], zoom: float = 1.0
    ) -> str:
        """
        Get all text within a screen rectangle.

        Args:
            rect: (x0, y0, x1, y1) in screen coordinates
            zoom: Current zoom level

        Returns:
            Text content in the rectangle
        """
        # Convert to PDF coordinates
        pdf_rect = (rect[0] / zoom, rect[1] / zoom, rect[2] / zoom, rect[3] / zoom)

        chars = self.text_layer.get_chars_in_rect(pdf_rect)
        return self.text_layer.get_text_from_chars(chars)

    def get_links_at_point(
        self, x: float, y: float, zoom: float = 1.0
    ) -> List[LinkInfo]:
        """Get all links at a point (for overlapping links)."""
        pdf_x = x / zoom
        pdf_y = y / zoom

        return [
            link for link in self.link_layer.links if link.contains_point(pdf_x, pdf_y)
        ]

    def search_text(
        self, search_term: str, case_sensitive: bool = False
    ) -> List[Tuple[float, float, float, float]]:
        """
        Search for text on this page.

        Args:
            search_term: Text to search for
            case_sensitive: Whether search is case-sensitive

        Returns:
            List of rectangles where text was found
        """
        flags = 0 if case_sensitive else fitz.TEXT_PRESERVE_WHITESPACE

        # Use fitz search which handles multi-word and regex
        rects = self.page.search_for(search_term, quads=False)

        return [(r.x0, r.y0, r.x1, r.y1) for r in rects]

    def clear_cache(self):
        """Clear the rendering cache to free memory."""
        self._pixmap_cache.clear()

    def unload(self):
        """Unload page data to free memory."""
        self._text_layer = None
        self._link_layer = None
        self._pixmap_cache.clear()
        self._page = None

    def preload_layers(self):
        """Preload text and link layers (for background loading)."""
        _ = self.text_layer
        _ = self.link_layer

    @property
    def has_text(self) -> bool:
        """Check if page has extractable text."""
        return len(self.text_layer) > 0

    @property
    def has_links(self) -> bool:
        """Check if page has clickable links."""
        return len(self.link_layer) > 0

    def __repr__(self) -> str:
        return f"PageModel(page={self.page_index}, size={self.width:.0f}x{self.height:.0f})"

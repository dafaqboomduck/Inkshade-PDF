"""
Link extraction and handling for PDF pages.
"""

from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, Tuple

import fitz


class LinkType(Enum):
    """Types of links in a PDF."""

    GOTO = "goto"  # Internal page navigation
    GOTO_R = "goto_r"  # Remote PDF link
    URI = "uri"  # External URL
    LAUNCH = "launch"  # Launch external application
    NAMED = "named"  # Named destination
    UNKNOWN = "unknown"


@dataclass
class LinkDestination:
    """Destination information for internal links."""

    page_num: int  # 0-based page number
    x: float = 0.0  # X position on page
    y: float = 0.0  # Y position on page
    zoom: Optional[float] = None  # Zoom level (if specified)


@dataclass
class LinkInfo:
    """Represents a clickable link in the PDF."""

    bbox: Tuple[float, float, float, float]  # x0, y0, x1, y1
    link_type: LinkType

    # For internal links (goto)
    destination: Optional[LinkDestination] = None

    # For external links (uri)
    uri: Optional[str] = None

    # For named destinations
    named_dest: Optional[str] = None

    # For file links
    file_path: Optional[str] = None

    # Original link data for debugging
    _raw_data: Optional[dict] = None

    def contains_point(self, x: float, y: float) -> bool:
        """Check if a point is within this link's bounds."""
        return self.bbox[0] <= x <= self.bbox[2] and self.bbox[1] <= y <= self.bbox[3]

    @property
    def display_text(self) -> str:
        """Get a displayable description of the link."""
        if self.link_type == LinkType.URI:
            return self.uri or "External Link"
        elif self.link_type == LinkType.GOTO:
            if self.destination:
                return f"Go to page {self.destination.page_num + 1}"
            return "Internal Link"
        elif self.link_type == LinkType.NAMED:
            return f"#{self.named_dest}" if self.named_dest else "Named Link"
        elif self.link_type == LinkType.LAUNCH:
            return self.file_path or "Open File"
        return "Link"


class PageLinkLayer:
    """
    Manages clickable links for a PDF page.

    Extracts and provides access to all interactive link regions.
    """

    # Mapping from fitz link kinds to our LinkType
    _LINK_TYPE_MAP = {
        fitz.LINK_NONE: LinkType.UNKNOWN,
        fitz.LINK_GOTO: LinkType.GOTO,
        fitz.LINK_GOTOR: LinkType.GOTO_R,
        fitz.LINK_URI: LinkType.URI,
        fitz.LINK_LAUNCH: LinkType.LAUNCH,
        fitz.LINK_NAMED: LinkType.NAMED,
    }

    def __init__(self, page: fitz.Page, doc: fitz.Document):
        self.page = page
        self.doc = doc
        self.links: List[LinkInfo] = []

        self._extract_links()

    def _extract_links(self):
        """Extract all links from the page."""
        try:
            raw_links = self.page.get_links()
        except Exception as e:
            print(f"Failed to extract links: {e}")
            return

        for link_data in raw_links:
            link_info = self._parse_link(link_data)
            if link_info:
                self.links.append(link_info)

    def _parse_link(self, link_data: dict) -> Optional[LinkInfo]:
        """Parse a raw link dictionary into a LinkInfo object."""
        # Get bounding box
        from_rect = link_data.get("from")
        if from_rect is None:
            return None

        # Handle both Rect objects and tuples
        if hasattr(from_rect, "__iter__"):
            bbox = tuple(from_rect)
        else:
            bbox = (from_rect.x0, from_rect.y0, from_rect.x1, from_rect.y1)

        # Get link type
        kind = link_data.get("kind", fitz.LINK_NONE)
        link_type = self._LINK_TYPE_MAP.get(kind, LinkType.UNKNOWN)

        # Create base link info
        link_info = LinkInfo(bbox=bbox, link_type=link_type, _raw_data=link_data)

        # Parse type-specific data
        if link_type == LinkType.GOTO:
            link_info.destination = self._parse_goto_destination(link_data)

        elif link_type == LinkType.GOTO_R:
            link_info.file_path = link_data.get("file", "")
            link_info.destination = self._parse_goto_destination(link_data)

        elif link_type == LinkType.URI:
            link_info.uri = link_data.get("uri", "")

        elif link_type == LinkType.LAUNCH:
            link_info.file_path = link_data.get("file", "")

        elif link_type == LinkType.NAMED:
            link_info.named_dest = link_data.get("name", "")
            # Try to resolve named destination
            resolved = self._resolve_named_destination(link_info.named_dest)
            if resolved:
                link_info.destination = resolved

        return link_info

    def _parse_goto_destination(self, link_data: dict) -> Optional[LinkDestination]:
        """Parse internal link destination."""
        page_num = link_data.get("page", -1)
        if page_num < 0:
            return None

        # Get target position
        to_point = link_data.get("to")
        x, y = 0.0, 0.0

        if to_point is not None:
            if hasattr(to_point, "x"):
                x, y = to_point.x, to_point.y
            elif isinstance(to_point, (tuple, list)) and len(to_point) >= 2:
                x, y = to_point[0], to_point[1]

        # Get zoom if specified
        zoom = link_data.get("zoom")

        return LinkDestination(page_num=page_num, x=x, y=y, zoom=zoom)

    def _resolve_named_destination(self, name: str) -> Optional[LinkDestination]:
        """Resolve a named destination to a page/position."""
        if not name or not self.doc:
            return None

        try:
            # Use document's resolve_link method
            dest = self.doc.resolve_link(f"#{name}")
            if dest and isinstance(dest, dict):
                page_num = dest.get("page", -1)
                if page_num >= 0:
                    to_point = dest.get("to")
                    x, y = 0.0, 0.0
                    if to_point:
                        x, y = getattr(to_point, "x", 0), getattr(to_point, "y", 0)
                    return LinkDestination(page_num=page_num, x=x, y=y)
        except Exception:
            pass

        return None

    def get_link_at_point(self, x: float, y: float) -> Optional[LinkInfo]:
        """
        Find the link at the given PDF coordinates.

        Returns the topmost link if multiple overlap.
        """
        # Check in reverse order (later links are on top)
        for link in reversed(self.links):
            if link.contains_point(x, y):
                return link
        return None

    def get_links_in_rect(
        self, rect: Tuple[float, float, float, float]
    ) -> List[LinkInfo]:
        """Get all links that intersect with a rectangle."""
        x0, y0, x1, y1 = rect
        result = []

        for link in self.links:
            # Check intersection
            if (
                link.bbox[0] <= x1
                and link.bbox[2] >= x0
                and link.bbox[1] <= y1
                and link.bbox[3] >= y0
            ):
                result.append(link)

        return result

    def get_all_link_rects(self) -> List[Tuple[float, float, float, float]]:
        """Get all link bounding boxes for visual indication."""
        return [link.bbox for link in self.links]

    def get_links_by_type(self, link_type: LinkType) -> List[LinkInfo]:
        """Get all links of a specific type."""
        return [link for link in self.links if link.link_type == link_type]

    @property
    def internal_links(self) -> List[LinkInfo]:
        """Get all internal navigation links."""
        return [
            link
            for link in self.links
            if link.link_type in (LinkType.GOTO, LinkType.NAMED)
        ]

    @property
    def external_links(self) -> List[LinkInfo]:
        """Get all external URL links."""
        return self.get_links_by_type(LinkType.URI)

    def __len__(self) -> int:
        return len(self.links)

    def __iter__(self):
        return iter(self.links)

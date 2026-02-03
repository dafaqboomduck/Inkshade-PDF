from dataclasses import dataclass, field
from enum import Enum
from typing import Any, List, Optional, Tuple

# ==============================================================================
# Types
# ==============================================================================


class LinkType(Enum):
    """Types of links in a PDF."""

    GOTO = "goto"  # Internal page navigation
    GOTO_R = "goto_r"  # Remote PDF link
    URI = "uri"  # External URL
    LAUNCH = "launch"  # Launch external application
    NAMED = "named"  # Named destination
    UNKNOWN = "unknown"


class InteractionType(Enum):
    """Type of interactive element at a point."""

    NONE = "none"
    TEXT = "text"
    LINK = "link"
    IMAGE = "image"
    ANNOTATION = "annotation"


# ==============================================================================
# Link Layer Objects
# ==============================================================================


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


# ==============================================================================
# Page Model Objects
# ==============================================================================


@dataclass
class InteractionResult:
    """Result of checking what's at a point."""

    type: InteractionType
    element: Any = None

    @property
    def is_interactive(self) -> bool:
        return self.type != InteractionType.NONE


# ==============================================================================
# Text Layer Objects
# ==============================================================================


@dataclass
class CharacterInfo:
    """Represents a single character with its position and metadata."""

    char: str
    bbox: Tuple[float, float, float, float]  # x0, y0, x1, y1
    origin: Tuple[float, float]  # baseline origin point
    span_index: int
    line_index: int
    block_index: int
    font_name: str
    font_size: float
    color: int  # Color as integer (needs conversion)

    # Computed index in the character list (set after extraction)
    global_index: int = -1

    def contains_point(self, x: float, y: float) -> bool:
        """Check if point is within character bounds."""
        return self.bbox[0] <= x <= self.bbox[2] and self.bbox[1] <= y <= self.bbox[3]


@dataclass
class SpanInfo:
    """A span of text with consistent formatting."""

    characters: List[CharacterInfo] = field(default_factory=list)
    font_name: str = ""
    font_size: float = 12.0
    color: int = 0
    flags: int = 0  # Font flags (bold, italic, etc.)
    bbox: Tuple[float, float, float, float] = (0, 0, 0, 0)

    @property
    def text(self) -> str:
        return "".join(c.char for c in self.characters)


@dataclass
class LineInfo:
    """A line of text containing multiple spans."""

    spans: List[SpanInfo] = field(default_factory=list)
    bbox: Tuple[float, float, float, float] = (0, 0, 0, 0)
    wmode: int = 0  # Writing mode (0=horizontal, 1=vertical)
    dir_vector: Tuple[float, float] = (1, 0)  # Text direction

    @property
    def text(self) -> str:
        return "".join(span.text for span in self.spans)

    @property
    def all_characters(self) -> List[CharacterInfo]:
        chars = []
        for span in self.spans:
            chars.extend(span.characters)
        return chars


@dataclass
class BlockInfo:
    """A block of text (paragraph or text region)."""

    lines: List[LineInfo] = field(default_factory=list)
    bbox: Tuple[float, float, float, float] = (0, 0, 0, 0)
    block_type: int = 0  # 0 = text, 1 = image

    @property
    def text(self) -> str:
        return "\n".join(line.text for line in self.lines)

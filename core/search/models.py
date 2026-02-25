from dataclasses import dataclass
from typing import Tuple


@dataclass
class SearchResult:
    """Represents a single search result."""

    page_index: int
    rect: Tuple[
        float, float, float, float, float, float
    ]  # x0, y0, x1, y1, width, height - NOW A TUPLE
    text: str = ""

    def to_tuple(self) -> Tuple[int, Tuple]:
        """Convert to legacy tuple format for compatibility."""
        return (self.page_index, self.rect)

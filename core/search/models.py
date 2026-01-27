import fitz  # PyMuPDF
from typing import Tuple
from dataclasses import dataclass

@dataclass
class SearchResult:
    """Represents a single search result."""
    page_index: int
    rect: fitz.Rect
    text: str = ""
    
    def to_tuple(self) -> Tuple[int, fitz.Rect]:
        """Convert to legacy tuple format for compatibility."""
        return (self.page_index, self.rect)
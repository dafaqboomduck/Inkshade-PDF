"""
Data classes for PDF page elements.
"""

from dataclasses import dataclass
from typing import List, Tuple, Optional
from PyQt5.QtGui import QPixmap, QPainterPath

@dataclass
class TextElement:
    """Represents a text span (word or phrase)"""
    text: str
    bbox: Tuple[float, float, float, float]  # x0, y0, x1, y1
    font_name: str
    font_size: float
    color: Tuple[int, int, int]  # RGB
    page_index: int
    chars: List[Tuple[str, Tuple[float, float, float, float]]]  # Individual characters for selection
    
@dataclass
class ImageElement:
    """Represents an embedded image"""
    bbox: Tuple[float, float, float, float]
    pixmap: QPixmap
    page_index: int
    transform: List[float]  # Transformation matrix
    
@dataclass
class VectorElement:
    """Represents a vector path (lines, curves, shapes)"""
    path: QPainterPath
    stroke_color: Optional[Tuple[int, int, int]]
    fill_color: Optional[Tuple[int, int, int]]
    line_width: float
    page_index: int
    
@dataclass
class LinkElement:
    """Represents a clickable link"""
    bbox: Tuple[float, float, float, float]
    link_type: str  # 'goto', 'uri', 'gotor', 'launch', 'named'
    destination: any  # Page number for internal links, URL for external
    page_index: int

@dataclass
class PageElements:
    """Container for all elements on a page"""
    texts: List[TextElement]
    images: List[ImageElement]
    vectors: List[VectorElement]
    links: List[LinkElement]
    width: float
    height: float
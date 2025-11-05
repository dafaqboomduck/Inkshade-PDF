from dataclasses import dataclass
from typing import List, Tuple
from enum import Enum

class AnnotationType(Enum):
    HIGHLIGHT = "highlight"
    UNDERLINE = "underline"

@dataclass
class Annotation:
    """Represents a single annotation on a PDF page."""
    page_index: int # 0-based page index
    annotation_type: AnnotationType
    color: Tuple[int, int, int] # RGB tuple (0-255)
    quads: List[List[float]] # List of quad coordinates [x0, y0, x1, y1, x2, y2, x3, y3]

    def to_dict(self):
        """Convert annotation to dictionary for JSON serialization."""
        return {
            'page_index': self.page_index,
            'type': self.annotation_type.value,
            'color': list(self.color),
            'quads': self.quads
        }
    
    @staticmethod
    def from_dict(data):
        """Create annotation from dictionary."""
        return Annotation(
            page_index=data['page_index'],
            annotation_type=AnnotationType(data['annotation_type']),
            color=tuple(data['color']),
            quads=data['quads']
        )

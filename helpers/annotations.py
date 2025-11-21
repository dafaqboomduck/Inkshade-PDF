from dataclasses import dataclass
from typing import List, Tuple, Optional
from enum import Enum

class AnnotationType(Enum):
    HIGHLIGHT = "highlight"
    UNDERLINE = "underline"
    FREEHAND = "freehand"
    RECTANGLE = "rectangle"
    CIRCLE = "circle"
    ARROW = "arrow"
    LINE = "line"

class ActionType(Enum):
    ADD = "add"
    REMOVE = "remove"
    MODIFY = "modify"   

@dataclass
class Annotation:
    """Represents a single annotation on a PDF page."""
    page_index: int # 0-based page index
    annotation_type: AnnotationType
    color: Tuple[int, int, int] # RGB tuple (0-255)
    
    # For text annotations (highlight, underline)
    quads: Optional[List[List[float]]] = None

    # For drawing annotations (freehand, shapes)
    points: Optional[List[Tuple[float, float]]] = None  # List of (x, y) coordinates

    # Shape-specific properties
    stroke_width: float = 2.0
    filled: bool = False

    def to_dict(self):
        """Convert annotation to dictionary for JSON serialization."""
        data = {
            'page_index': self.page_index,
            'type': self.annotation_type.value,
            'color': list(self.color),
            'stroke_width': self.stroke_width,
            'filled': self.filled
        }
        
        if self.quads is not None:
            data['quads'] = self.quads
        
        if self.points is not None:
            data['points'] = [[x, y] for x, y in self.points]
        
        return data
    
    @staticmethod
    def from_dict(data):
        """Create annotation from dictionary."""
        quads = data.get('quads')
        points_data = data.get('points')
        points = [tuple(p) for p in points_data] if points_data else None
        
        return Annotation(
            page_index=data['page_index'],
            annotation_type=AnnotationType(data['type']),
            color=tuple(data['color']),
            quads=quads,
            points=points,
            stroke_width=data.get('stroke_width', 2.0),
            filled=data.get('filled', False)
        )

@dataclass
class AnnotationAction:
    """Represents an action that can be undone/redone."""
    action_type: ActionType
    annotation: Annotation
    old_annotation: Optional[Annotation] = None  # For modify actions
    page_index: int = -1
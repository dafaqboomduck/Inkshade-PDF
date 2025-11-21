from typing import List, Optional, Tuple
import json
import os
import hashlib
import copy

from helpers.annotations import AnnotationType, Annotation

class UndoRedoStack:
    """Manages undo/redo operations for annotations."""
    
    def __init__(self, max_size=50):
        self.undo_stack = []
        self.redo_stack = []
        self.max_size = max_size
    
    def push_state(self, annotations: List[Annotation]):
        """Push current state to undo stack."""
        # Deep copy the annotations
        state = [copy.deepcopy(ann) for ann in annotations]
        self.undo_stack.append(state)
        
        # Clear redo stack when new action is performed
        self.redo_stack.clear()
        
        # Limit stack size
        if len(self.undo_stack) > self.max_size:
            self.undo_stack.pop(0)
    
    def can_undo(self) -> bool:
        """Check if undo is available."""
        return len(self.undo_stack) > 0
    
    def can_redo(self) -> bool:
        """Check if redo is available."""
        return len(self.redo_stack) > 0
    
    def undo(self, current_state: List[Annotation]) -> Optional[List[Annotation]]:
        """Perform undo and return the previous state."""
        if not self.can_undo():
            return None
        
        # Save current state to redo stack
        self.redo_stack.append([copy.deepcopy(ann) for ann in current_state])
        
        # Pop and return previous state
        return self.undo_stack.pop()
    
    def redo(self, current_state: List[Annotation]) -> Optional[List[Annotation]]:
        """Perform redo and return the next state."""
        if not self.can_redo():
            return None
        
        # Save current state to undo stack
        self.undo_stack.append([copy.deepcopy(ann) for ann in current_state])
        
        # Pop and return next state
        return self.redo_stack.pop()
    
    def clear(self):
        """Clear both stacks."""
        self.undo_stack.clear()
        self.redo_stack.clear()


class AnnotationManager:
    """Manages all annotations for a PDF document with undo/redo support."""

    def __init__(self):
        self.annotations: List[Annotation] = []
        self.pdf_path = None
        self.has_unsaved_changes = False
        self.json_file_path = None
        self._app_data_dir = None
        self.undo_redo_stack = UndoRedoStack()
        
        # For tracking selected annotation
        self.selected_annotation = None

    def _get_app_data_dir(self):
        """Get or create the app's data directory for storing annotations."""
        if self._app_data_dir:
            return self._app_data_dir
            
        # Use user's app data directory
        if os.name == 'nt':  # Windows
            base_dir = os.environ.get('APPDATA', os.path.expanduser('~'))
        else:  # macOS, Linux
            base_dir = os.path.expanduser('~/.local/share')
        
        app_dir = os.path.join(base_dir, 'InkshadePDF', 'annotations')
        os.makedirs(app_dir, exist_ok=True)
        self._app_data_dir = app_dir
        return app_dir

    def set_pdf_path(self, pdf_path: str):
        """Set the current PDF path and determine JSON file location."""
        self.pdf_path = pdf_path
        
        # Create a hash of the PDF path to use as filename
        # This ensures unique storage per PDF regardless of location
        path_hash = hashlib.md5(pdf_path.encode()).hexdigest()
        
        # Store JSON in app data directory with hashed filename
        app_dir = self._get_app_data_dir()
        self.json_file_path = os.path.join(app_dir, f"{path_hash}.json")
        
    def add_annotation(self, annotation: Annotation):
        """Add a new annotation with undo support."""
        # Save state before adding
        self.undo_redo_stack.push_state(self.annotations)
        
        self.annotations.append(annotation)
        self.has_unsaved_changes = True
        self._auto_save()
        
    def remove_annotation(self, annotation: Annotation):
        """Remove an annotation with undo support."""
        if annotation in self.annotations:
            # Save state before removing
            self.undo_redo_stack.push_state(self.annotations)
            
            self.annotations.remove(annotation)
            self.has_unsaved_changes = True
            self.selected_annotation = None
            self._auto_save()
            return True
        return False
    
    def update_annotation(self, old_annotation: Annotation, new_annotation: Annotation):
        """Update an existing annotation with undo support."""
        try:
            index = self.annotations.index(old_annotation)
            # Save state before updating
            self.undo_redo_stack.push_state(self.annotations)
            
            self.annotations[index] = new_annotation
            self.has_unsaved_changes = True
            self._auto_save()
            return True
        except ValueError:
            return False

    def get_annotations_for_page(self, page_index: int) -> List[Annotation]:
        """Get all annotations for a specific page"""
        return [ann for ann in self.annotations if ann.page_index == page_index]
    
    def get_annotation_at_point(self, page_index: int, x: float, y: float, zoom: float = 1.0) -> Optional[Annotation]:
        """
        Get annotation at a specific point on a page.
        Returns the topmost annotation if multiple overlap.
        """
        page_annotations = self.get_annotations_for_page(page_index)
        
        # Check in reverse order (topmost first)
        for ann in reversed(page_annotations):
            if self._point_in_annotation(ann, x, y, zoom):
                return ann
        return None
    
    def _point_in_annotation(self, annotation: Annotation, x: float, y: float, zoom: float) -> bool:
        """Check if a point is within an annotation's bounds."""
        # Convert point to PDF coordinates
        pdf_x = x / zoom
        pdf_y = y / zoom
        
        if annotation.annotation_type in [AnnotationType.HIGHLIGHT, AnnotationType.UNDERLINE]:
            # Check if point is in any of the quads
            if annotation.quads:
                for quad in annotation.quads:
                    # quad format: [x0, y0, x1, y1, x2, y2, x3, y3]
                    # We only need the bounding box
                    min_x = min(quad[0], quad[2], quad[4], quad[6])
                    max_x = max(quad[0], quad[2], quad[4], quad[6])
                    min_y = min(quad[1], quad[3], quad[5], quad[7])
                    max_y = max(quad[1], quad[3], quad[5], quad[7])
                    
                    if min_x <= pdf_x <= max_x and min_y <= pdf_y <= max_y:
                        return True
        
        elif annotation.annotation_type == AnnotationType.FREEHAND:
            # Check if point is near the freehand path
            if annotation.points and len(annotation.points) >= 2:
                # Simplified check: see if point is near any segment
                tolerance = max(annotation.stroke_width + 2.0, 5.0) / zoom  # Use stroke width with minimum tolerance
                
                for i in range(len(annotation.points) - 1):
                    p1 = annotation.points[i]
                    p2 = annotation.points[i + 1]
                    
                    # Check distance to line segment
                    if self._point_near_line(pdf_x, pdf_y, p1[0], p1[1], p2[0], p2[1], tolerance):
                        return True
        
        # Add similar checks for other annotation types if needed
        return False
    
    def _point_near_line(self, px: float, py: float, x1: float, y1: float, x2: float, y2: float, tolerance: float) -> bool:
        """Check if a point is near a line segment."""
        # Calculate distance from point to line segment
        line_length_sq = (x2 - x1) ** 2 + (y2 - y1) ** 2
        
        if line_length_sq == 0:
            # Line is a point
            dist = ((px - x1) ** 2 + (py - y1) ** 2) ** 0.5
            return dist <= tolerance
        
        # Calculate projection parameter
        t = max(0, min(1, ((px - x1) * (x2 - x1) + (py - y1) * (y2 - y1)) / line_length_sq))
        
        # Find nearest point on line segment
        nearest_x = x1 + t * (x2 - x1)
        nearest_y = y1 + t * (y2 - y1)
        
        # Calculate distance
        dist = ((px - nearest_x) ** 2 + (py - nearest_y) ** 2) ** 0.5
        return dist <= tolerance
    
    def undo(self) -> bool:
        """Perform undo operation."""
        if not self.undo_redo_stack.can_undo():
            return False
        
        previous_state = self.undo_redo_stack.undo(self.annotations)
        if previous_state is not None:
            self.annotations = previous_state
            self.has_unsaved_changes = True
            self.selected_annotation = None
            self._auto_save()
            return True
        return False
    
    def redo(self) -> bool:
        """Perform redo operation."""
        if not self.undo_redo_stack.can_redo():
            return False
        
        next_state = self.undo_redo_stack.redo(self.annotations)
        if next_state is not None:
            self.annotations = next_state
            self.has_unsaved_changes = True
            self.selected_annotation = None
            self._auto_save()
            return True
        return False
    
    def can_undo(self) -> bool:
        """Check if undo is available."""
        return self.undo_redo_stack.can_undo()
    
    def can_redo(self) -> bool:
        """Check if redo is available."""
        return self.undo_redo_stack.can_redo()
    
    def clear_all(self):
        """Clear all annotations"""
        self.annotations.clear()
        self.has_unsaved_changes = False
        self.pdf_path = None
        self.json_file_path = None
        self.selected_annotation = None
        self.undo_redo_stack.clear()

    def _auto_save(self):
        """Automatically save annotations to JSON file."""
        if self.json_file_path:
            try:
                self.save_to_json(self.json_file_path)
            except Exception as e:
                print(f"Auto-save failed: {e}")

    def save_to_json(self, file_path: str = None):
        """Save annotations to a JSON file."""
        if file_path is None:
            file_path = self.json_file_path
            
        if not file_path:
            return
            
        data = {
            'pdf_path': self.pdf_path,
            'annotations': [ann.to_dict() for ann in self.annotations]
        }
        with open(file_path, 'w') as f:
            json.dump(data, f, indent=2)
    
    def load_from_json(self, file_path: str = None):
        """Load annotations from a JSON file."""
        if file_path is None:
            file_path = self.json_file_path
            
        if not file_path or not os.path.exists(file_path):
            return False
            
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
            
            self.pdf_path = data.get('pdf_path')
            self.annotations = [Annotation.from_dict(ann_data) for ann_data in data['annotations']]
            self.has_unsaved_changes = False
            self.undo_redo_stack.clear()  # Clear undo/redo when loading
            return True
        except Exception as e:
            print(f"Failed to load annotations: {e}")
            return False
    
    def auto_load_annotations(self):
        """Try to automatically load annotations for the current PDF."""
        if self.json_file_path and os.path.exists(self.json_file_path):
            return self.load_from_json()
        return False
    
    def delete_json_file(self):
        """Delete the JSON annotation file."""
        if self.json_file_path and os.path.exists(self.json_file_path):
            try:
                os.remove(self.json_file_path)
                self.has_unsaved_changes = False
            except Exception as e:
                print(f"Failed to delete JSON file: {e}")
    
    def mark_saved(self):
        """Mark all changes as saved."""
        self.has_unsaved_changes = False
    
    def get_annotation_count(self) -> int:
        """Get total number of annotations."""
        return len(self.annotations)
"""
Main annotation manager that coordinates all annotation operations.
Fixed to properly track unsaved changes.
"""
from typing import List, Optional
from .models import Annotation, AnnotationType
from .undo_redo import UndoRedoStack
from .persistence import AnnotationPersistence


class AnnotationManager:
    """Manages all annotations for a PDF document with undo/redo support."""
    
    def __init__(self):
        self.annotations: List[Annotation] = []
        self.pdf_path: Optional[str] = None
        self.has_unsaved_changes: bool = False
        
        # Components
        self.undo_redo_stack = UndoRedoStack()
        self.persistence = AnnotationPersistence()
        
        # For tracking selected annotation
        self.selected_annotation: Optional[Annotation] = None
        
        # Track the initial state to detect real changes
        self.initial_annotations: List[Annotation] = []
    
    def set_pdf_path(self, pdf_path: str) -> None:
        """
        Set the current PDF path.
        
        Args:
            pdf_path: Path to the PDF file
        """
        self.pdf_path = pdf_path
    
    def add_annotation(self, annotation: Annotation) -> None:
        """
        Add a new annotation with undo support.
        
        Args:
            annotation: Annotation to add
        """
        # Save state before adding
        self.undo_redo_stack.push_state(self.annotations)
        
        self.annotations.append(annotation)
        self._check_for_changes()
        self._auto_save()
    
    def remove_annotation(self, annotation: Annotation) -> bool:
        """
        Remove an annotation with undo support.
        
        Args:
            annotation: Annotation to remove
            
        Returns:
            True if annotation was found and removed
        """
        if annotation in self.annotations:
            # Save state before removing
            self.undo_redo_stack.push_state(self.annotations)
            
            self.annotations.remove(annotation)
            self.selected_annotation = None
            self._check_for_changes()
            self._auto_save()
            return True
        return False
    
    def update_annotation(self, old_annotation: Annotation, 
                         new_annotation: Annotation) -> bool:
        """
        Update an existing annotation with undo support.
        
        Args:
            old_annotation: Annotation to replace
            new_annotation: New annotation data
            
        Returns:
            True if annotation was found and updated
        """
        try:
            index = self.annotations.index(old_annotation)
            # Save state before updating
            self.undo_redo_stack.push_state(self.annotations)
            
            self.annotations[index] = new_annotation
            self._check_for_changes()
            self._auto_save()
            return True
        except ValueError:
            return False
    
    def _check_for_changes(self) -> None:
        """
        Check if current annotations differ from initial state.
        Updates has_unsaved_changes flag accordingly.
        """
        # Compare current annotations with initial state
        if len(self.annotations) != len(self.initial_annotations):
            self.has_unsaved_changes = True
            return
        
        # Check if all annotations match (order doesn't matter)
        # Create a simplified comparison that ignores object identity
        current_set = set(
            (ann.page_index, ann.annotation_type.value, ann.color, 
             str(ann.quads), str(ann.points), ann.stroke_width, ann.filled)
            for ann in self.annotations
        )
        
        initial_set = set(
            (ann.page_index, ann.annotation_type.value, ann.color,
             str(ann.quads), str(ann.points), ann.stroke_width, ann.filled)
            for ann in self.initial_annotations
        )
        
        self.has_unsaved_changes = (current_set != initial_set)
    
    def get_annotations_for_page(self, page_index: int) -> List[Annotation]:
        """
        Get all annotations for a specific page.
        
        Args:
            page_index: 0-based page index
            
        Returns:
            List of annotations on the specified page
        """
        return [ann for ann in self.annotations if ann.page_index == page_index]
    
    def get_annotation_at_point(self, page_index: int, x: float, y: float, 
                                zoom: float = 1.0) -> Optional[Annotation]:
        """
        Get annotation at a specific point on a page.
        
        Args:
            page_index: 0-based page index
            x: X coordinate in screen pixels
            y: Y coordinate in screen pixels
            zoom: Current zoom level
            
        Returns:
            The topmost annotation at the point, or None
        """
        page_annotations = self.get_annotations_for_page(page_index)
        
        # Check in reverse order (topmost first)
        for ann in reversed(page_annotations):
            if self._point_in_annotation(ann, x, y, zoom):
                return ann
        return None
    
    def _point_in_annotation(self, annotation: Annotation, x: float, 
                            y: float, zoom: float) -> bool:
        """
        Check if a point is within an annotation's bounds.
        
        Args:
            annotation: Annotation to check
            x: X coordinate in screen pixels
            y: Y coordinate in screen pixels
            zoom: Current zoom level
            
        Returns:
            True if point is within annotation bounds
        """
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
                tolerance = max(annotation.stroke_width + 2.0, 5.0) / zoom
                
                for i in range(len(annotation.points) - 1):
                    p1 = annotation.points[i]
                    p2 = annotation.points[i + 1]
                    
                    # Check distance to line segment
                    if self._point_near_line(pdf_x, pdf_y, p1[0], p1[1], 
                                           p2[0], p2[1], tolerance):
                        return True
        
        return False
    
    def _point_near_line(self, px: float, py: float, x1: float, y1: float, 
                        x2: float, y2: float, tolerance: float) -> bool:
        """
        Check if a point is near a line segment.
        
        Args:
            px, py: Point coordinates
            x1, y1, x2, y2: Line segment endpoints
            tolerance: Maximum distance to consider "near"
            
        Returns:
            True if point is within tolerance of the line segment
        """
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
        """
        Perform undo operation.
        
        Returns:
            True if undo was successful
        """
        if not self.undo_redo_stack.can_undo():
            return False
        
        previous_state = self.undo_redo_stack.undo(self.annotations)
        if previous_state is not None:
            self.annotations = previous_state
            self.selected_annotation = None
            self._check_for_changes()
            self._auto_save()
            return True
        return False
    
    def redo(self) -> bool:
        """
        Perform redo operation.
        
        Returns:
            True if redo was successful
        """
        if not self.undo_redo_stack.can_redo():
            return False
        
        next_state = self.undo_redo_stack.redo(self.annotations)
        if next_state is not None:
            self.annotations = next_state
            self.selected_annotation = None
            self._check_for_changes()
            self._auto_save()
            return True
        return False
    
    def can_undo(self) -> bool:
        """Check if undo is available."""
        return self.undo_redo_stack.can_undo()
    
    def can_redo(self) -> bool:
        """Check if redo is available."""
        return self.undo_redo_stack.can_redo()
    
    def clear_all(self) -> None:
        """Clear all annotations and reset state."""
        self.annotations.clear()
        self.initial_annotations.clear()
        self.has_unsaved_changes = False
        self.pdf_path = None
        self.selected_annotation = None
        self.undo_redo_stack.clear()
    
    def _auto_save(self) -> None:
        """Automatically save annotations to JSON file."""
        if self.pdf_path:
            try:
                self.persistence.save_to_json(self.annotations, self.pdf_path)
            except Exception as e:
                print(f"Auto-save failed: {e}")
    
    def save_to_json(self, file_path: Optional[str] = None) -> bool:
        """
        Save annotations to a JSON file.
        
        Args:
            file_path: Optional custom path for the JSON file
            
        Returns:
            True if save was successful
        """
        if not self.pdf_path:
            return False
        
        return self.persistence.save_to_json(self.annotations, self.pdf_path, file_path)
    
    def load_from_json(self, file_path: Optional[str] = None) -> bool:
        """
        Load annotations from a JSON file.
        
        Args:
            file_path: Optional custom path for the JSON file
            
        Returns:
            True if load was successful
        """
        if not self.pdf_path:
            return False
        
        annotations, success = self.persistence.load_from_json(self.pdf_path, file_path)
        if success:
            self.annotations = annotations
            # Store initial state for change detection
            import copy
            self.initial_annotations = [copy.deepcopy(ann) for ann in annotations]
            self.has_unsaved_changes = False
            self.undo_redo_stack.clear()
        return success
    
    def auto_load_annotations(self) -> bool:
        """
        Try to automatically load annotations for the current PDF.
        
        Returns:
            True if annotations were loaded
        """
        if self.pdf_path and self.persistence.has_saved_annotations(self.pdf_path):
            return self.load_from_json()
        return False
    
    def delete_json_file(self) -> bool:
        """
        Delete the JSON annotation file.
        
        Returns:
            True if deletion was successful
        """
        if self.pdf_path:
            success = self.persistence.delete_json_file(self.pdf_path)
            if success:
                self.has_unsaved_changes = False
                self.initial_annotations.clear()
            return success
        return False
    
    def mark_saved(self) -> None:
        """Mark all changes as saved and update initial state."""
        import copy
        self.initial_annotations = [copy.deepcopy(ann) for ann in self.annotations]
        self.has_unsaved_changes = False
    
    def get_annotation_count(self) -> int:
        """Get total number of annotations."""
        return len(self.annotations)
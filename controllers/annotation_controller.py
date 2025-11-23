"""
Controller for managing annotation operations.
"""
from typing import List, Optional, Tuple
from PyQt5.QtCore import QObject, pyqtSignal
from PyQt5.QtWidgets import QMessageBox, QColorDialog, QWidget
from PyQt5.QtGui import QColor

from core.annotations import AnnotationManager, Annotation, AnnotationType


class AnnotationController(QObject):
    """Handles all annotation-related operations and user interactions."""
    
    # Signals
    annotations_changed = pyqtSignal()  # Emitted when annotations change
    annotation_selected = pyqtSignal(object)  # Emitted when annotation is selected
    
    def __init__(self, annotation_manager: AnnotationManager, parent: QWidget = None):
        super().__init__()
        self.annotation_manager = annotation_manager
        self.parent_widget = parent
    
    def create_text_annotation(self, page_index: int, selected_words: set,
                              annotation_type: AnnotationType, 
                              color: Tuple[int, int, int]) -> bool:
        """
        Create a text-based annotation (highlight/underline) from selected words.
        
        Args:
            page_index: Page where annotation is created
            selected_words: Set of selected word data
            annotation_type: Type of annotation (HIGHLIGHT or UNDERLINE)
            color: RGB color tuple
            
        Returns:
            True if annotation was created successfully
        """
        if not selected_words:
            QMessageBox.information(
                self.parent_widget, 
                "No Selection", 
                "Please select text before creating an annotation."
            )
            return False
        
        # Convert selected words to quads
        quads = self._words_to_quads(selected_words)
        
        if not quads:
            return False
        
        # Create annotation
        annotation = Annotation(
            page_index=page_index,
            annotation_type=annotation_type,
            color=color,
            quads=quads
        )
        
        self.annotation_manager.add_annotation(annotation)
        self.annotations_changed.emit()
        return True
    
    def create_drawing_annotation(self, page_index: int, 
                                 points: List[Tuple[float, float]],
                                 tool_type: AnnotationType,
                                 color: Tuple[int, int, int],
                                 stroke_width: float,
                                 filled: bool) -> bool:
        """
        Create a drawing annotation.
        
        Args:
            page_index: Page where annotation is created
            points: List of (x, y) coordinates
            tool_type: Drawing tool type
            color: RGB color tuple
            stroke_width: Width of the stroke
            filled: Whether shape should be filled
            
        Returns:
            True if annotation was created successfully
        """
        if len(points) < 2:
            return False
        
        annotation = Annotation(
            page_index=page_index,
            annotation_type=tool_type,
            color=color,
            points=points.copy(),
            stroke_width=stroke_width,
            filled=filled
        )
        
        self.annotation_manager.add_annotation(annotation)
        self.annotations_changed.emit()
        return True
    
    def delete_annotation(self, annotation: Annotation) -> bool:
        """
        Delete an annotation with user confirmation.
        
        Args:
            annotation: Annotation to delete
            
        Returns:
            True if annotation was deleted
        """
        reply = QMessageBox.question(
            self.parent_widget,
            "Delete Annotation",
            "Are you sure you want to delete this annotation?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            if self.annotation_manager.remove_annotation(annotation):
                self.annotations_changed.emit()
                return True
        
        return False
    
    def edit_annotation_color(self, annotation: Annotation) -> bool:
        """
        Edit the color of an annotation.
        
        Args:
            annotation: Annotation to edit
            
        Returns:
            True if color was changed
        """
        initial_color = QColor(
            annotation.color[0], 
            annotation.color[1], 
            annotation.color[2]
        )
        
        color = QColorDialog.getColor(
            initial_color, 
            self.parent_widget, 
            "Choose New Color"
        )
        
        if color.isValid():
            # Create updated annotation
            new_annotation = Annotation(
                page_index=annotation.page_index,
                annotation_type=annotation.annotation_type,
                color=(color.red(), color.green(), color.blue()),
                quads=annotation.quads,
                points=annotation.points,
                stroke_width=annotation.stroke_width,
                filled=annotation.filled
            )
            
            # Update in manager
            if self.annotation_manager.update_annotation(annotation, new_annotation):
                self.annotations_changed.emit()
                return True
        
        return False
    
    def select_annotation(self, annotation: Optional[Annotation]) -> None:
        """
        Select or deselect an annotation.
        
        Args:
            annotation: Annotation to select, or None to deselect
        """
        self.annotation_manager.selected_annotation = annotation
        self.annotation_selected.emit(annotation)
    
    def undo(self) -> bool:
        """
        Undo the last annotation action.
        
        Returns:
            True if undo was successful
        """
        if self.annotation_manager.undo():
            self.annotations_changed.emit()
            return True
        return False
    
    def redo(self) -> bool:
        """
        Redo the last undone annotation action.
        
        Returns:
            True if redo was successful
        """
        if self.annotation_manager.redo():
            self.annotations_changed.emit()
            return True
        return False
    
    def can_undo(self) -> bool:
        """Check if undo is available."""
        return self.annotation_manager.can_undo()
    
    def can_redo(self) -> bool:
        """Check if redo is available."""
        return self.annotation_manager.can_redo()
    
    def save_to_pdf(self, pdf_path: str, output_path: str) -> bool:
        """
        Save annotations to a PDF file.
        
        Args:
            pdf_path: Path to source PDF
            output_path: Path for output PDF
            
        Returns:
            True if save was successful
        """
        if self.annotation_manager.get_annotation_count() == 0:
            QMessageBox.information(
                self.parent_widget, 
                "No Annotations", 
                "There are no annotations to save."
            )
            return False
        
        # Export functionality would be handled here
        # This would integrate with PDFExporter
        return True
    
    def load_annotations(self, pdf_path: str) -> int:
        """
        Auto-load annotations for a PDF.
        
        Args:
            pdf_path: Path to the PDF file
            
        Returns:
            Number of annotations loaded
        """
        self.annotation_manager.set_pdf_path(pdf_path)
        
        if self.annotation_manager.auto_load_annotations():
            count = self.annotation_manager.get_annotation_count()
            self.annotations_changed.emit()
            return count
        
        return 0
    
    def check_unsaved_changes(self) -> Optional[int]:
        """
        Check for unsaved changes and prompt user.
        
        Returns:
            QMessageBox result or None if no unsaved changes
        """
        if not self.annotation_manager.has_unsaved_changes:
            return None
        
        return QMessageBox.question(
            self.parent_widget,
            "Unsaved Changes",
            "You have unsaved annotations. Do you want to save them?",
            QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
            QMessageBox.Save
        )
    
    def _words_to_quads(self, selected_words: set) -> List[List[float]]:
        """
        Convert selected words to quad coordinates.
        
        Args:
            selected_words: Set of word data tuples
            
        Returns:
            List of quad coordinates
        """
        quads = []
        lines = {}
        
        # Group words by line
        for word_info in selected_words:
            line_key = (word_info[5], word_info[6])
            if line_key not in lines:
                lines[line_key] = []
            lines[line_key].append(word_info)
        
        # Create quads for each line
        for line_key, words_in_line in lines.items():
            words_in_line.sort(key=lambda x: x[0])
            
            min_x = min(word[0] for word in words_in_line)
            max_x = max(word[2] for word in words_in_line)
            min_y = min(word[1] for word in words_in_line)
            max_y = max(word[3] for word in words_in_line)
            
            quad = [min_x, min_y, max_x, min_y, 
                   min_x, max_y, max_x, max_y]
            quads.append(quad)
        
        return quads
    
    def get_annotations_for_page(self, page_index: int) -> List[Annotation]:
        """
        Get annotations for a specific page.
        
        Args:
            page_index: 0-based page index
            
        Returns:
            List of annotations on the page
        """
        return self.annotation_manager.get_annotations_for_page(page_index)
    
    def get_annotation_at_point(self, page_index: int, x: float, y: float, 
                                zoom: float) -> Optional[Annotation]:
        """
        Get annotation at a specific point.
        
        Args:
            page_index: Page index
            x: X coordinate
            y: Y coordinate
            zoom: Current zoom level
            
        Returns:
            Annotation at the point or None
        """
        return self.annotation_manager.get_annotation_at_point(
            page_index, x, y, zoom
        )
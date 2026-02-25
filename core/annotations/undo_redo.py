"""
Undo/Redo functionality for annotations.
"""
from typing import List, Optional
import copy
from .models import Annotation


class UndoRedoStack:
    """Manages undo/redo operations for annotations."""
    
    def __init__(self, max_size: int = 50):
        """
        Initialize the undo/redo stack.
        
        Args:
            max_size: Maximum number of states to keep in history
        """
        self.undo_stack: List[List[Annotation]] = []
        self.redo_stack: List[List[Annotation]] = []
        self.max_size = max_size
    
    def push_state(self, annotations: List[Annotation]) -> None:
        """
        Push current state to undo stack.
        
        Args:
            annotations: Current list of annotations to save
        """
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
        """
        Perform undo and return the previous state.
        
        Args:
            current_state: Current annotations before undo
            
        Returns:
            Previous state of annotations, or None if undo not available
        """
        if not self.can_undo():
            return None
        
        # Save current state to redo stack
        self.redo_stack.append([copy.deepcopy(ann) for ann in current_state])
        
        # Pop and return previous state
        return self.undo_stack.pop()
    
    def redo(self, current_state: List[Annotation]) -> Optional[List[Annotation]]:
        """
        Perform redo and return the next state.
        
        Args:
            current_state: Current annotations before redo
            
        Returns:
            Next state of annotations, or None if redo not available
        """
        if not self.can_redo():
            return None
        
        # Save current state to undo stack
        self.undo_stack.append([copy.deepcopy(ann) for ann in current_state])
        
        # Pop and return next state
        return self.redo_stack.pop()
    
    def clear(self) -> None:
        """Clear both stacks."""
        self.undo_stack.clear()
        self.redo_stack.clear()
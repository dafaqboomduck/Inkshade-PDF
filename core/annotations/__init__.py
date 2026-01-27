"""
Annotation system for PDF documents.
"""
from .models import Annotation, AnnotationType, ActionType, AnnotationAction
from .manager import AnnotationManager
from .undo_redo import UndoRedoStack
from .persistence import AnnotationPersistence

__all__ = [
    'Annotation',
    'AnnotationType', 
    'ActionType',
    'AnnotationAction',
    'AnnotationManager',
    'UndoRedoStack',
    'AnnotationPersistence'
]
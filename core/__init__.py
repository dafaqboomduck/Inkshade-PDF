"""
Core business logic for Inkshade PDF Reader.
"""
from .annotations import AnnotationManager, Annotation, AnnotationType

__all__ = ['AnnotationManager', 'Annotation', 'AnnotationType']
"""
Core business logic for Inkshade PDF Reader.
"""

from .annotations import Annotation, AnnotationManager, AnnotationType

# New page architecture
from .page import (
    CharacterInfo,
    LinkInfo,
    LinkType,
    PageLinkLayer,
    PageModel,
    PageTextLayer,
)
from .selection import SelectionManager

__all__ = [
    "AnnotationManager",
    "Annotation",
    "AnnotationType",
    "PageModel",
    "PageTextLayer",
    "PageLinkLayer",
    "CharacterInfo",
    "LinkInfo",
    "LinkType",
    "SelectionManager",
]

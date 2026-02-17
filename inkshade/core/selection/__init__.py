"""
Text selection management for PDF documents.
"""

from .models import PageSelection, SelectionAnchor
from .selection_manager import SelectionManager

__all__ = ["SelectionManager", "SelectionAnchor", "PageSelection"]

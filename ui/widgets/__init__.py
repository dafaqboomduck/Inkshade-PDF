"""
Custom widgets for PDF viewing and interaction.
"""

from .narration_player import NarrationPlayerBar
from .page_label import InteractivePageLabel
from .pdf_viewer import PDFViewer
from .toc_widget import TOCWidget

__all__ = [
    "InteractivePageLabel",
    "NarrationPlayerBar",
    "PDFViewer",
    "TOCWidget",
]

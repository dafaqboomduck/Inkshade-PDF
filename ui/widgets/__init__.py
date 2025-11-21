"""
Custom widgets for PDF viewing and interaction.
"""
from .page_label import ClickablePageLabel
from .pdf_viewer import PDFViewer
from .toc_widget import TOCWidget

__all__ = ['ClickablePageLabel', 'PDFViewer', 'TOCWidget']
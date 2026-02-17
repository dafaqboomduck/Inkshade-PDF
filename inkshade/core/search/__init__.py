"""
Search functionality for PDF documents.
"""

from .search_engine import PDFSearchEngine, SearchResult
from .search_highlight import SearchHighlight
from .search_worker import SearchWorker

__all__ = ["PDFSearchEngine", "SearchResult", "SearchHighlight", "SearchWorker"]

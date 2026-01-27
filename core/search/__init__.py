"""
Search functionality for PDF documents.
"""
from .search_engine import PDFSearchEngine, SearchResult
from .search_highlight import SearchHighlight

__all__ = ['PDFSearchEngine', 'SearchResult', 'SearchHighlight']
"""
PDF search functionality with result management.
"""

from typing import List, Optional, Tuple

import fitz  # PyMuPDF

from .models import SearchResult


class PDFSearchEngine:
    """Handles text search operations within PDF documents."""

    def __init__(self):
        self.search_results: List[SearchResult] = []
        self.current_search_index: int = -1
        self.current_search_term: str = ""
        self._doc: Optional[fitz.Document] = None
        self._is_searching: bool = False

    def set_document(self, doc: fitz.Document) -> None:
        """
        Set the PDF document to search in.

        Args:
            doc: PyMuPDF document object
        """
        self._doc = doc
        self.clear_search()

    def clear_search(self) -> None:
        """Reset all search state."""
        self.search_results = []
        self.current_search_index = -1
        self.current_search_term = ""
        self._is_searching = False

    def start_search(self, search_term: str) -> None:
        """
        Prepare for a new search (called before threaded search).

        Args:
            search_term: The term to search for
        """
        self.current_search_term = search_term
        self.search_results = []
        self.current_search_index = -1
        self._is_searching = True

    def add_result(self, result: SearchResult) -> None:
        """
        Add a search result (called from worker thread via signal).

        Args:
            result: SearchResult to add
        """
        self.search_results.append(result)

    def finish_search(self) -> None:
        """Mark search as complete."""
        self._is_searching = False

    def is_searching(self) -> bool:
        """Check if a search is in progress."""
        return self._is_searching

    def get_document(self) -> Optional[fitz.Document]:
        """Get the current document for the worker thread."""
        return self._doc

    def get_all_results(self) -> List[Tuple[int, tuple]]:
        """
        Get all search results in legacy format.

        Returns:
            List of (page_index, rect) tuples
        """
        return [r.to_tuple() for r in self.search_results]

    def get_current_result(self) -> Tuple[Optional[int], Optional[tuple]]:
        """
        Get the current search result.

        Returns:
            Current result as (page_index, rect) tuple, or (None, None)
        """
        if 0 <= self.current_search_index < len(self.search_results):
            return self.search_results[self.current_search_index].to_tuple()
        return None, None

    def next_result(self) -> Tuple[Optional[int], Optional[tuple]]:
        """
        Move to the next search result.

        Returns:
            Next result as (page_index, rect) tuple, or (None, None)
        """
        if not self.search_results:
            return None, None

        self.current_search_index = (self.current_search_index + 1) % len(
            self.search_results
        )
        return self.search_results[self.current_search_index].to_tuple()

    def previous_result(self) -> Tuple[Optional[int], Optional[tuple]]:
        """
        Move to the previous search result.

        Returns:
            Previous result as (page_index, rect) tuple, or (None, None)
        """
        if not self.search_results:
            return None, None

        self.current_search_index = (
            self.current_search_index - 1 + len(self.search_results)
        ) % len(self.search_results)
        return self.search_results[self.current_search_index].to_tuple()

    def get_result_count(self) -> int:
        """Get total number of search results."""
        return len(self.search_results)

    def get_current_index(self) -> int:
        """Get current result index (0-based, -1 if none)."""
        return self.current_search_index

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

    # In core/search/search_engine.py

    def execute_search(self, search_term: str) -> int:
        """
        Perform a new search across the entire document.
        """
        if not self._doc or not search_term:
            self.clear_search()
            return 0

        if search_term == self.current_search_term:
            return len(self.search_results)

        self.current_search_term = search_term
        self.search_results = []

        for page_idx in range(self._doc.page_count):
            page = self._doc.load_page(page_idx)
            quads_on_page = page.search_for(search_term, quads=True)
            rects_on_page = [q.rect for q in quads_on_page]
            merged_rects = self._merge_consecutive_rects(rects_on_page)

            for rect in merged_rects:
                # CONVERT TO TUPLE IMMEDIATELY
                rect_tuple = (
                    rect.x0,
                    rect.y0,
                    rect.x1,
                    rect.y1,
                    rect.width,
                    rect.height,
                )
                result = SearchResult(
                    page_index=page_idx,
                    rect=rect_tuple,  # Store tuple, not fitz.Rect
                    text=search_term,
                )
                self.search_results.append(result)

        self.current_search_index = -1
        return len(self.search_results)

    def get_all_results(self) -> List[Tuple[int, fitz.Rect]]:
        """
        Get all search results in legacy format.

        Returns:
            List of (page_index, rect) tuples
        """
        return [r.to_tuple() for r in self.search_results]

    def get_current_result(self) -> Optional[Tuple[int, fitz.Rect]]:
        """
        Get the current search result.

        Returns:
            Current result as (page_index, rect) tuple, or None
        """
        if 0 <= self.current_search_index < len(self.search_results):
            return self.search_results[self.current_search_index].to_tuple()
        return None, None

    def next_result(self) -> Optional[Tuple[int, fitz.Rect]]:
        """
        Move to the next search result.

        Returns:
            Next result as (page_index, rect) tuple, or None
        """
        if not self.search_results:
            return None, None

        self.current_search_index = (self.current_search_index + 1) % len(
            self.search_results
        )
        return self.search_results[self.current_search_index].to_tuple()

    def previous_result(self) -> Optional[Tuple[int, fitz.Rect]]:
        """
        Move to the previous search result.

        Returns:
            Previous result as (page_index, rect) tuple, or None
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

    def _merge_rects(self, rects: List[fitz.Rect]) -> Optional[fitz.Rect]:
        """
        Find the bounding box of a list of rectangles.

        Args:
            rects: List of rectangles to merge

        Returns:
            Merged bounding box, or None if list is empty
        """
        if not rects:
            return None

        min_x0 = min(r.x0 for r in rects)
        min_y0 = min(r.y0 for r in rects)
        max_x1 = max(r.x1 for r in rects)
        max_y1 = max(r.y1 for r in rects)

        return fitz.Rect(min_x0, min_y0, max_x1, max_y1)

    def _merge_consecutive_rects(
        self, rects: List[fitz.Rect], y_tolerance: float = 3.0, max_height: float = 18.0
    ) -> List[Tuple]:
        """Groups and merges rectangles, returns tuples."""
        if not rects:
            return []

        merged_results = []
        rects.sort(key=lambda r: (r.y0, r.x0))

        current_group = [rects[0]]
        current_merged_rect = self._merge_rects(current_group)

        for i in range(1, len(rects)):
            current_rect = rects[i]
            vertical_gap = current_rect.y0 - current_merged_rect.y1
            projected_y1 = max(current_rect.y1, current_merged_rect.y1)
            projected_height = projected_y1 - current_merged_rect.y0
            is_contiguous = (vertical_gap <= y_tolerance) and (
                projected_height <= max_height
            )

            if is_contiguous:
                current_group.append(current_rect)
                current_merged_rect = self._merge_rects(current_group)
            else:
                merged_results.append(current_merged_rect)
                current_group = [current_rect]
                current_merged_rect = self._merge_rects(current_group)

        if current_group:
            merged_results.append(current_merged_rect)

        # Convert all to tuples before returning
        return merged_results  # These are still fitz.Rect, converted in execute_search

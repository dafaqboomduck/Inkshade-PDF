"""
PDF search functionality with result management.
"""
import fitz  # PyMuPDF
from typing import List, Tuple, Optional
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
    
    def execute_search(self, search_term: str) -> int:
        """
        Perform a new search across the entire document.
        
        Args:
            search_term: Text to search for
            
        Returns:
            Number of results found
        """
        if not self._doc or not search_term:
            self.clear_search()
            return 0
        
        # Only search if term has changed
        if search_term == self.current_search_term:
            return len(self.search_results)
        
        self.current_search_term = search_term
        self.search_results = []
        
        # Search through all pages
        for page_idx in range(self._doc.page_count):
            page = self._doc.load_page(page_idx)
            
            # Use quads for better phrase search
            quads_on_page = page.search_for(search_term, quads=True)
            
            # Convert quads to rects
            rects_on_page = [q.rect for q in quads_on_page]
            
            # Merge consecutive rects on the same line
            merged_rects = self._merge_consecutive_rects(rects_on_page)
            
            for rect in merged_rects:
                result = SearchResult(
                    page_index=page_idx,
                    rect=rect,
                    text=search_term
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
        
        self.current_search_index = (self.current_search_index + 1) % len(self.search_results)
        return self.search_results[self.current_search_index].to_tuple()
    
    def previous_result(self) -> Optional[Tuple[int, fitz.Rect]]:
        """
        Move to the previous search result.
        
        Returns:
            Previous result as (page_index, rect) tuple, or None
        """
        if not self.search_results:
            return None, None
        
        self.current_search_index = (self.current_search_index - 1 + len(self.search_results)) % len(self.search_results)
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
    
    def _merge_consecutive_rects(self, rects: List[fitz.Rect], 
                                 y_tolerance: float = 3.0, 
                                 max_height: float = 18.0) -> List[fitz.Rect]:
        """
        Groups and merges rectangles based on vertical proximity.
        
        This prevents search results from spanning multiple lines when
        they shouldn't.
        
        Args:
            rects: List of rectangles to merge
            y_tolerance: Maximum vertical gap to consider consecutive
            max_height: Maximum height for merged result
            
        Returns:
            List of merged rectangles
        """
        if not rects:
            return []
        
        merged_results = []
        
        # Sort by Y-coordinate (top-to-bottom) then by X-coordinate (left-to-right)
        rects.sort(key=lambda r: (r.y0, r.x0))
        
        current_group = [rects[0]]
        current_merged_rect = self._merge_rects(current_group)
        
        for i in range(1, len(rects)):
            current_rect = rects[i]
            
            # Check vertical proximity (strict for same line/split word)
            vertical_gap = current_rect.y0 - current_merged_rect.y1
            
            # Check total height to prevent multi-line merging
            projected_y1 = max(current_rect.y1, current_merged_rect.y1)
            projected_height = projected_y1 - current_merged_rect.y0
            
            # Merge if gap is tiny AND combined height is reasonable
            is_contiguous = (vertical_gap <= y_tolerance) and (projected_height <= max_height)
            
            if is_contiguous:
                # Part of the same logical search match
                current_group.append(current_rect)
                current_merged_rect = self._merge_rects(current_group)
            else:
                # A vertical break occurred or merged box would be too tall
                merged_results.append(current_merged_rect)
                
                # Start a new group
                current_group = [current_rect]
                current_merged_rect = self._merge_rects(current_group)
        
        # Append the last group
        if current_group:
            merged_results.append(current_merged_rect)
        
        return merged_results
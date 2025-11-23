import fitz  # PyMuPDF
from typing import Tuple, List
from .search_engine import PDFSearchEngine

class SearchHighlight:
    """Helper class for managing search highlight rendering."""
    
    @staticmethod
    def get_highlights_for_page(search_engine: PDFSearchEngine, 
                                page_index: int) -> Tuple[List[fitz.Rect], int]:
        """
        Get search highlights for a specific page.
        
        Args:
            search_engine: The search engine with results
            page_index: Page to get highlights for
            
        Returns:
            Tuple of (list of rectangles, current highlight index on page)
        """
        # Get all results for this page
        page_rects = []
        current_idx_on_page = -1
        
        for i, result in enumerate(search_engine.search_results):
            if result.page_index == page_index:
                page_rects.append(result.rect)
                
                # Check if this is the current result
                if i == search_engine.current_search_index:
                    current_idx_on_page = len(page_rects) - 1
        
        return page_rects, current_idx_on_page
import fitz # PyMuPDF
from PyQt5.QtGui import QImage, QPixmap
from PyQt5.QtWidgets import QMessageBox

class PDFDocumentReader:
    def __init__(self):
        self.doc = None
        self.total_pages = 0
        self.search_results = []
        self.current_search_index = -1
        self.current_search_term = ""
        self.toc = []

    def load_pdf(self, file_path):
        """Loads a PDF document and returns the number of pages."""
        try:
            self.doc = fitz.open(file_path)
            self.total_pages = self.doc.page_count
            self._clear_search()

            self.toc = self.doc.get_toc()

            return True, self.total_pages
        except Exception as e:
            QMessageBox.critical(None, "Error", f"Error loading PDF: {e}")
            return False, 0

    def render_page(self, page_index, zoom_level, dark_mode):
        """Renders a single page of the PDF to a pixmap and extracts its text and word data."""
        if not self.doc or page_index >= self.total_pages:
            return None, None, None
        
        try:
            page = self.doc.load_page(page_index)
            mat = fitz.Matrix(zoom_level, zoom_level)
            
            pix = page.get_pixmap(matrix=mat)
            img = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format_RGB888)
            if dark_mode:
                img.invertPixels()
            pixmap = QPixmap.fromImage(img)
            
            text_data = page.get_text("dict", sort=True)
            word_data = page.get_text("words", sort=True)
            
            return pixmap, text_data, word_data
        except Exception as e:
            QMessageBox.critical(None, "Error", f"Error rendering page {page_index+1}: {e}")
            return None, None, None

    def _clear_search(self):
        """Resets the search state."""
        self.search_results = []
        self.current_search_index = -1
        self.current_search_term = ""
    
    def _merge_rects(self, rects):
        """Helper to find the bounding box of a list of fitz.Rect objects."""
        if not rects:
            return None

        min_x0 = min(r.x0 for r in rects)
        min_y0 = min(r.y0 for r in rects)
        max_x1 = max(r.x1 for r in rects)
        max_y1 = max(r.y1 for r in rects)
        
        return fitz.Rect(min_x0, min_y0, max_x1, max_y1)

    def _merge_consecutive_rects(self, rects, y_tolerance=3.0, max_height=18.0):
        """
        Groups and merges rectangles based on strict vertical proximity (y_tolerance) 
        and enforces a maximum height (max_height) to prevent merging results 
        that span multiple lines of text.
        """
        if not rects:
            return []

        merged_results = []
        
        # 1. Sort by Y-coordinate (top-to-bottom) then by X-coordinate (left-to-right)
        rects.sort(key=lambda r: (r.y0, r.x0))

        current_group = [rects[0]]
        current_merged_rect = self._merge_rects(current_group)

        for i in range(1, len(rects)):
            current_rect = rects[i]
            
            # 1. Vertical Proximity Check (strict for same line/split word)
            vertical_gap = current_rect.y0 - current_merged_rect.y1
            
            # 2. Total Height Check: Don't merge if the resulting box would be too tall.
            # Normal line height is usually around 12-15 units. We use 18.0 as a safe upper bound.
            projected_y1 = max(current_rect.y1, current_merged_rect.y1)
            projected_height = projected_y1 - current_merged_rect.y0
            
            # Merge Condition: The gap must be tiny AND the combined height must be reasonable.
            is_contiguous = (vertical_gap <= y_tolerance) and (projected_height <= max_height)

            if is_contiguous:
                # Part of the same logical search match, add to the current group
                current_group.append(current_rect)
                current_merged_rect = self._merge_rects(current_group)
            else:
                # A vertical break occurred or the projected merged box is too tall.
                merged_results.append(current_merged_rect)
                
                # Start a new group
                current_group = [current_rect]
                current_merged_rect = self._merge_rects(current_group)

        # Merge and append the last group
        if current_group:
            merged_results.append(current_merged_rect)
            
        return merged_results
    
    def get_toc(self):
        """Returns the parsed table of contents."""
        return self.toc

    def execute_search(self, search_term):
        """
        Performs a new search across the entire document for a given term,
        using proximity-based merging to combine fragmented highlights.
        """
        if not search_term:
            self._clear_search()
            return 0
        
        if search_term != self.current_search_term:
            self.current_search_term = search_term
            self.search_results = []
            
            for i in range(self.total_pages):
                page = self.doc.load_page(i)
                
                # Use quads=True as it is generally best practice for phrase search
                quads_on_page = page.search_for(search_term, quads=True)
                
                # Convert quads to rects
                rects_on_page = [q.rect for q in quads_on_page]
                
                # Use the new helper to merge consecutive rects on the same line
                merged_rects = self._merge_consecutive_rects(rects_on_page)

                for rect in merged_rects:
                    self.search_results.append((i, rect))
            
            self.current_search_index = -1
            
        return len(self.search_results)

    def get_search_result_info(self):
        """Returns the current search result page index and rectangle."""
        if self.current_search_index == -1:
            return None, None
        return self.search_results[self.current_search_index]

    def next_search_result(self):
        """Moves to the next search result and returns its info."""
        if not self.search_results: return None, None
        self.current_search_index = (self.current_search_index + 1) % len(self.search_results)
        print(self.search_results[self.current_search_index])
        return self.search_results[self.current_search_index]

    def prev_search_result(self):
        """Moves to the previous search result and returns its info."""
        if not self.search_results: return None, None
        self.current_search_index = (self.current_search_index - 1 + len(self.search_results)) % len(self.search_results)
        return self.search_results[self.current_search_index]
    
    def get_all_search_results(self):
        """Returns the full list of search results."""
        return self.search_results
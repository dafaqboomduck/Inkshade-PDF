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

    def load_pdf(self, file_path):
        """Loads a PDF document and returns the number of pages."""
        try:
            self.doc = fitz.open(file_path)
            self.total_pages = self.doc.page_count
            self._clear_search()
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
        
    def execute_search(self, search_term):
        """
        Performs a new search across the entire document for a given term.
        Returns the number of results found.
        """
        if not search_term:
            self._clear_search()
            return 0
        
        if search_term != self.current_search_term:
            self.current_search_term = search_term
            self.search_results = []
            for i in range(self.total_pages):
                page = self.doc.load_page(i)
                results_on_page = page.search_for(search_term, quads=False)
                for rect in results_on_page:
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
        return self.search_results[self.current_search_index]

    def prev_search_result(self):
        """Moves to the previous search result and returns its info."""
        if not self.search_results: return None, None
        self.current_search_index = (self.current_search_index - 1 + len(self.search_results)) % len(self.search_results)
        return self.search_results[self.current_search_index]
    
    def get_all_search_results(self):
        """Returns the full list of search results."""
        return self.search_results
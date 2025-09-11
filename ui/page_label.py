from PyQt5.QtCore import Qt, QRect, QRectF
from PyQt5.QtGui import QPainter, QColor
from PyQt5.QtWidgets import QLabel

# Custom widget to display a page image and handle text selection
class ClickablePageLabel(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.text_data = None  # Stores the text blocks, lines, and spans
        self.word_data = None  # New: Stores word-level data from PyMuPDF
        self.zoom_level = 1.0
        self.start_pos = None
        self.end_pos = None
        self.selection_rects = []
        self.dark_mode = False # Tracks the mode for selection color
        self.setMouseTracking(True) # To allow selection highlighting

    def set_page_data(self, pixmap, text_data, word_data, zoom_level, dark_mode):
        """Sets the page image, text data, and zoom level."""
        self.setPixmap(pixmap)
        self.text_data = text_data
        self.word_data = word_data
        self.zoom_level = zoom_level
        self.dark_mode = dark_mode
        self.selection_rects = []
        self.update() # Repaint the widget

    def mousePressEvent(self, event):
        """Records the starting position for a new text selection."""
        if event.button() == Qt.LeftButton:
            self.start_pos = event.pos()
            self.end_pos = None
            self.selection_rects = []
            self.update()

    def mouseMoveEvent(self, event):
        """Updates the end position as the user drags and highlights text."""
        if event.buttons() & Qt.LeftButton and self.word_data:
            self.end_pos = event.pos()
            self.selection_rects = self.get_selection_rects()
            self.update()
        
    def mouseReleaseEvent(self, event):
        """Finalizes the selection on mouse button release."""
        if event.button() == Qt.LeftButton and self.word_data:
            self.end_pos = event.pos()
            self.selection_rects = self.get_selection_rects()
            self.update()

    def paintEvent(self, event):
        """Draws the page image and then overlays the selection highlight."""
        super().paintEvent(event)
        if self.selection_rects:
            painter = QPainter(self)
            painter.setPen(Qt.NoPen)
            # Change selection color based on dark mode
            if self.dark_mode:
                painter.setBrush(QColor(255, 255, 0, 128)) # Yellow for dark mode
            else:
                painter.setBrush(QColor(0, 0, 255, 100)) # Blue for light mode
            for rect in self.selection_rects:
                painter.drawRect(rect)
            painter.end()

    def get_selection_rects(self):
        """
        Calculates the rectangles to highlight based on the mouse selection area.
        This now operates on a word-by-word basis.
        """
        if not self.start_pos or not self.end_pos or not self.word_data:
            return []

        rects = []
        selection_rect = QRect(self.start_pos, self.end_pos).normalized()
        
        # Iterate over the word data (PyMuPDF returns a tuple: (x0, y0, x1, y1, word, block_no, line_no, word_no))
        for word_info in self.word_data:
            bbox = word_info[:4]
            word_rect = QRectF(
                bbox[0] * self.zoom_level,
                bbox[1] * self.zoom_level,
                (bbox[2] - bbox[0]) * self.zoom_level,
                (bbox[3] - bbox[1]) * self.zoom_level
            ).toRect()
            
            if selection_rect.intersects(word_rect):
                rects.append(word_rect)
        return rects
    
    def get_selected_text(self):
        """
        Extracts the actual text string from the selected words.
        """
        if not self.start_pos or not self.end_pos or not self.word_data:
            return ""

        selected_words = []
        selection_rect = QRect(self.start_pos, self.end_pos).normalized()

        for word_info in self.word_data:
            bbox = word_info[:4]
            word_rect = QRectF(
                bbox[0] * self.zoom_level,
                bbox[1] * self.zoom_level,
                (bbox[2] - bbox[0]) * self.zoom_level,
                (bbox[3] - bbox[1]) * self.zoom_level
            ).toRect()
            
            if selection_rect.intersects(word_rect):
                selected_words.append(word_info[4]) # The fifth element is the word text
        
        return " ".join(selected_words)
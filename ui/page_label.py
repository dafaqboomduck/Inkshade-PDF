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
        self.selected_words = set()  # Store selected words as a set for robust tracking
        self.line_word_map = {} # A cache to map line coordinates to word data
        self._selection_at_start = set() # Store selection state at drag start

    def set_page_data(self, pixmap, text_data, word_data, zoom_level, dark_mode):
        """Sets the page image, text data, and zoom level."""
        self.setPixmap(pixmap)
        self.text_data = text_data
        self.word_data = word_data
        self.zoom_level = zoom_level
        self.dark_mode = dark_mode
        self.selection_rects = []
        self.selected_words = set()
        self._build_line_word_map()
        self.update() # Repaint the widget

    def _build_line_word_map(self):
        """Builds a map of (block_no, line_no) to a list of word data tuples."""
        self.line_word_map = {}
        if self.word_data:
            for word_info in self.word_data:
                block_no, line_no = word_info[5], word_info[6]
                key = (block_no, line_no)
                if key not in self.line_word_map:
                    self.line_word_map[key] = []
                self.line_word_map[key].append(word_info)

    def mousePressEvent(self, event):
        """Records the starting position for a new text selection."""
        if event.button() == Qt.LeftButton:
            word_at_pos = self._get_word_at_pos(event.pos())
            
            # If the click is on an empty space and Ctrl is not held, clear all selections.
            if not word_at_pos and not (event.modifiers() & Qt.ControlModifier):
                self.selected_words.clear()
                self.selection_rects = []
                self.start_pos = None  # Prevent a drag from starting
                self.end_pos = None
                self.update()
                return # Exit the function as no selection is initiated

            self.start_pos = event.pos()
            self.end_pos = None
            self._selection_at_start = self.selected_words.copy()
            self.update()

    def mouseMoveEvent(self, event):
        """Updates the end position as the user drags and highlights text."""
        if event.buttons() & Qt.LeftButton and self.word_data and self.start_pos:
            self.end_pos = event.pos()
            self._update_selection(event.modifiers())
            self.update()
        
    def mouseReleaseEvent(self, event):
        """Finalizes the selection on mouse button release."""
        if event.button() == Qt.LeftButton and self.word_data and self.start_pos:
            self.end_pos = event.pos()
            self._update_selection(event.modifiers())
            self.update()

    def _get_word_at_pos(self, pos):
        """Finds the word at a given QPoint, returning its data tuple or None."""
        if not self.word_data or not pos:
            return None
        
        for word_info in self.word_data:
            bbox = word_info[:4]
            word_rect = QRectF(
                bbox[0] * self.zoom_level,
                bbox[1] * self.zoom_level,
                (bbox[2] - bbox[0]) * self.zoom_level,
                (bbox[3] - bbox[1]) * self.zoom_level
            ).toRect()
            
            if word_rect.contains(pos):
                return word_info
        return None

    def _update_selection(self, modifiers):
        """Internal method to update the set of selected words based on the drag area and line boundaries."""
        if not self.start_pos or not self.end_pos or not self.word_data:
            return

        drag_rect = QRect(self.start_pos, self.end_pos).normalized()
        all_words_in_order = sorted(self.word_data, key=lambda x: (x[5], x[6], x[7]))

        start_word = self._get_word_at_pos(self.start_pos)
        end_word = self._get_word_at_pos(self.end_pos)

        if not start_word or not end_word:
            self.selection_rects = self._get_merged_selection_rects()
            return
        
        start_index = all_words_in_order.index(start_word)
        end_index = all_words_in_order.index(end_word)
        
        min_index = min(start_index, end_index)
        max_index = max(start_index, end_index)

        # Get the words within the drag range
        words_in_drag = set(all_words_in_order[min_index:max_index + 1])
        
        if modifiers & Qt.ControlModifier:
            # If Ctrl is held, toggle the state of words in the drag range
            self.selected_words = self._selection_at_start.symmetric_difference(words_in_drag)
        else:
            # If no Ctrl, determine intent (select vs. deselect) and update
            # The intent is to select if the starting word was not already selected
            is_starting_from_selected = start_word in self._selection_at_start
            
            if is_starting_from_selected:
                self.selected_words = self._selection_at_start.difference(words_in_drag)
            else:
                self.selected_words = words_in_drag

        self.selection_rects = self._get_merged_selection_rects()

    def _get_merged_selection_rects(self):
        """
        Calculates and merges rectangles for each selected line for cleaner highlighting.
        """
        if not self.selected_words:
            return []
        
        # Group selected words by line
        lines_to_highlight = {}
        for word_info in self.selected_words:
            key = (word_info[5], word_info[6]) # (block_no, line_no)
            if key not in lines_to_highlight:
                lines_to_highlight[key] = []
            lines_to_highlight[key].append(word_info)
            
        merged_rects = []
        for words_in_line in lines_to_highlight.values():
            if not words_in_line:
                continue
            
            # Sort words in the line by their x-coordinate to handle left-to-right selection
            sorted_words = sorted(words_in_line, key=lambda x: x[0])
            
            # Find the total bounding box for the words in this line
            line_bbox = sorted_words[0][:4]
            for word in sorted_words[1:]:
                line_bbox = (
                    min(line_bbox[0], word[0]),
                    min(line_bbox[1], word[1]),
                    max(line_bbox[2], word[2]),
                    max(line_bbox[3], word[3])
                )
            
            line_rect = QRectF(
                line_bbox[0] * self.zoom_level,
                line_bbox[1] * self.zoom_level,
                (line_bbox[2] - line_bbox[0]) * self.zoom_level,
                (line_bbox[3] - line_bbox[1]) * self.zoom_level
            ).toRect()
            merged_rects.append(line_rect)
        
        return merged_rects

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
        Calculates the rectangles to highlight from the set of selected words.
        This method is now a simplified proxy to the line-based method.
        """
        return self._get_merged_selection_rects()
    
    def get_selected_text(self):
        """
        Extracts the actual text string from the selected words.
        """
        if not self.selected_words:
            return ""

        # Sort the selected words by their y-coordinate and then x-coordinate
        sorted_words = sorted(list(self.selected_words), key=lambda x: (x[1], x[0]))
        
        # Build the final string, adding newlines between lines
        text_lines = []
        current_line_key = None
        current_line_words = []
        for word_info in sorted_words:
            line_key = (word_info[5], word_info[6])
            if current_line_key is None:
                current_line_key = line_key
            
            if line_key != current_line_key:
                text_lines.append(" ".join(current_line_words))
                current_line_key = line_key
                current_line_words = []
            
            current_line_words.append(word_info[4])
        
        if current_line_words:
            text_lines.append(" ".join(current_line_words))

        return "\n".join(text_lines)

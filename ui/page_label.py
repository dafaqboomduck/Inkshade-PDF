from PyQt5.QtCore import Qt, QRect, QRectF
from PyQt5.QtGui import QPainter, QColor, QBrush
from PyQt5.QtWidgets import QLabel

# Custom widget to display a page image and handle text selection
class ClickablePageLabel(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.text_data = None
        self.word_data = None
        self.zoom_level = 1.0
        self.start_pos = None
        self.end_pos = None
        self.selection_rects = []
        self.dark_mode = False
        self.setMouseTracking(True)
        self.selected_words = set()
        self.line_word_map = {}
        self._selection_at_start = set()
        
        self.search_highlights = []
        self.current_search_highlight_index = -1

    def set_page_data(self, pixmap, text_data, word_data, zoom_level, dark_mode, search_highlights=None, current_highlight_index=-1):
        self.setPixmap(pixmap)
        self.text_data = text_data
        self.word_data = word_data
        self.zoom_level = zoom_level
        self.dark_mode = dark_mode
        self.selection_rects = []
        self.selected_words = set()
        
        self.search_highlights = search_highlights if search_highlights else []
        self.current_search_highlight_index = current_highlight_index

        self._build_line_word_map()
        self.update()

    def set_search_highlights(self, highlights, current_index=-1):
        self.search_highlights = highlights
        self.current_search_highlight_index = current_index
        self.update()

    def _build_line_word_map(self):
        self.line_word_map = {}
        if self.word_data:
            for word_info in self.word_data:
                block_no, line_no = word_info[5], word_info[6]
                key = (block_no, line_no)
                if key not in self.line_word_map:
                    self.line_word_map[key] = []
                self.line_word_map[key].append(word_info)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            word_at_pos = self._get_word_at_pos(event.pos())
            
            if not word_at_pos and not (event.modifiers() & Qt.ControlModifier):
                self.selected_words.clear()
                self.selection_rects = []
                self.start_pos = None
                self.end_pos = None
                self.update()
                return

            self.start_pos = event.pos()
            self.end_pos = None
            self._selection_at_start = self.selected_words.copy()
            self.update()

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.LeftButton and self.word_data and self.start_pos:
            self.end_pos = event.pos()
            self._update_selection(event.modifiers())
            self.update()
        
    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self.word_data and self.start_pos:
            self.end_pos = event.pos()
            self._update_selection(event.modifiers())
            self.update()

    def _get_word_at_pos(self, pos):
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

        words_in_drag = set(all_words_in_order[min_index:max_index + 1])
        
        if modifiers & Qt.ControlModifier:
            self.selected_words = self._selection_at_start.symmetric_difference(words_in_drag)
        else:
            is_starting_from_selected = start_word in self._selection_at_start
            
            if is_starting_from_selected:
                self.selected_words = self._selection_at_start.difference(words_in_drag)
            else:
                self.selected_words = words_in_drag

        self.selection_rects = self._get_merged_selection_rects()

    def _get_merged_selection_rects(self):
        """
        Generates non-overlapping selection rectangles for each line containing
        selected words. The height of each rectangle is determined by the bounding
        box of the words on that specific line, ensuring no vertical overlap.
        """
        if not self.selected_words:
            return []
        
        # Group selected words by line
        lines_to_highlight = {}
        for word_info in self.selected_words:
            key = (word_info[5], word_info[6])
            if key not in lines_to_highlight:
                lines_to_highlight[key] = []
            lines_to_highlight[key].append(word_info)
            
        selection_rects = []
        for words_in_line in lines_to_highlight.values():
            if not words_in_line:
                continue
            
            # Find the min/max x and min/max y for all words in the line
            min_x = min(word[0] for word in words_in_line)
            max_x = max(word[2] for word in words_in_line)
            min_y = min(word[1] for word in words_in_line)
            max_y = max(word[3] for word in words_in_line)
            
            line_rect = QRectF(
                min_x * self.zoom_level,
                min_y * self.zoom_level,
                (max_x - min_x) * self.zoom_level,
                (max_y - min_y) * self.zoom_level
            ).toRect()
            selection_rects.append(line_rect)
        
        return selection_rects

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # 1. Draw search highlights (underneath text selection)
        if self.search_highlights and self.current_search_highlight_index != -1:
            if self.dark_mode:
                highlight_color = QColor(255, 255, 0, 150) # Yellow for current highlight in dark mode
            else:
                highlight_color = QColor(76, 91, 154, 200) # Blue for current highlight in light mode

            rect = self.search_highlights[self.current_search_highlight_index]
            highlight_rect = QRectF(
                rect.x0 * self.zoom_level,
                rect.y0 * self.zoom_level,
                rect.width * self.zoom_level,
                rect.height * self.zoom_level
            )
            
            painter.fillRect(highlight_rect, QBrush(highlight_color))


        # 2. Draw text selection highlights
        if self.selection_rects:
            painter.setPen(Qt.NoPen)
            if self.dark_mode:
                painter.setBrush(QColor(255, 255, 0, 100))
            else:
                painter.setBrush(QColor(76, 91, 154, 150))
            for rect in self.selection_rects:
                painter.drawRect(rect)
        
        painter.end()
    
    def get_selection_rects(self):
        return self.selection_rects
    
    def get_selected_text(self):
        if not self.selected_words:
            return ""

        sorted_words = sorted(list(self.selected_words), key=lambda x: (x[1], x[0]))
        
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

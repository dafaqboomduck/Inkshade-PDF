from PyQt5.QtCore import Qt, QRect, QRectF
from PyQt5.QtGui import QPainter, QColor, QBrush, QImage
from PyQt5.QtWidgets import QLabel
from core.user_input import UserInputHandler

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

        self.input_handler = UserInputHandler(parent)

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
        self.input_handler.handle_page_label_mouse_press(self, event)

    def mouseMoveEvent(self, event):
        self.input_handler.handle_page_label_mouse_move(self, event)
        
    def mouseReleaseEvent(self, event):
        self.input_handler.handle_page_label_mouse_release(self, event)

    def paintEvent(self, event):
        # 1. First, call the superclass's paintEvent to draw the QPixmap (the page image)
        super().paintEvent(event)
        
        # 2. Initialize the QPainter for the widget
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # --- Start of new QImage Buffer logic ---
        
        # Create a QImage buffer with the size of the widget and make it transparent
        buffer = QImage(self.size(), QImage.Format_ARGB32_Premultiplied)
        buffer.fill(Qt.transparent)
        
        # Initialize the QPainter for the buffer
        buf_painter = QPainter(buffer)
        buf_painter.setCompositionMode(QPainter.CompositionMode_Source)
        buf_painter.setRenderHint(QPainter.Antialiasing)
        buf_painter.setPen(Qt.NoPen)
        
        # --- Draw Search Highlights onto the buffer ---
        
        # Draw all non-current search highlights first (optional: you might want to draw them all the same way)
        # The original code only drew the *current* highlight, so we'll stick to that, 
        # but adjust the color/brush logic.
        if 0 <= self.current_search_highlight_index < len(self.search_highlights):
            current_rect = self.search_highlights[self.current_search_highlight_index]
            current_highlight_rect = QRectF(
                current_rect.x0 * self.zoom_level,
                current_rect.y0 * self.zoom_level,
                current_rect.width * self.zoom_level,
                current_rect.height * self.zoom_level
            )
            # Choose color for the current search highlight
            if self.dark_mode:
                current_highlight_color = QColor(255, 255, 0, 100) # Yellow (dark mode)
            else:
                current_highlight_color = QColor(0, 89, 195, 100) # Blue (light mode)
                
            buf_painter.setBrush(QBrush(current_highlight_color))
            buf_painter.drawRect(current_highlight_rect)

        # --- Draw Text Selection Highlights onto the buffer ---

        if self.selection_rects:
            # Choose color for the text selection highlights
            if self.dark_mode:
                selection_color = QColor(255, 255, 0, 100) # Yellow (dark mode)
            else:
                selection_color = QColor(0, 89, 195, 100) # Blue (light mode)
                
            # NOTE: If you want text selection to be *above* search highlights, 
            # ensure its color is distinct or adjust the drawing order.
            buf_painter.setBrush(QBrush(selection_color))
            
            for rect in self.selection_rects:
                # The rects in self.selection_rects are already scaled (or should be)
                # as they are QRect objects, but let's assume they are already correct
                # for drawing on the widget surface (which is the buffer size here).
                buf_painter.drawRect(rect) 
        
        buf_painter.end()

        # 3. Now paint the combined buffer onto the widget
        painter.setCompositionMode(QPainter.CompositionMode_SourceOver)
        painter.drawImage(0, 0, buffer)
        
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

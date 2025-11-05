from PyQt5.QtCore import Qt, QRect, QRectF, QPointF
from PyQt5.QtGui import QPainter, QColor, QBrush, QImage, QPen, QPainterPath
from PyQt5.QtWidgets import QLabel
import math
from core.user_input import UserInputHandler
from core.annotation_manager import AnnotationType

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
        
        # Store annotations for this page
        self.annotations = []

        self.input_handler = UserInputHandler(parent)
        
        # NEW: Drawing state
        self.is_drawing_mode = False
        self.current_drawing_tool = AnnotationType.FREEHAND
        self.current_drawing_color = (255, 0, 0)
        self.current_drawing_stroke_width = 2.0
        self.current_drawing_filled = False
        self.current_drawing_points = []  # Points for current shape being drawn
        self.is_currently_drawing = False  # Whether user is actively drawing right now

    def set_page_data(self, pixmap, text_data, word_data, zoom_level, dark_mode, search_highlights=None, current_highlight_index=-1, annotations=None):
        self.setPixmap(pixmap)
        self.text_data = text_data
        self.word_data = word_data
        self.zoom_level = zoom_level
        self.dark_mode = dark_mode
        self.selection_rects = []
        self.selected_words = set()
        
        self.search_highlights = search_highlights if search_highlights else []
        self.current_search_highlight_index = current_highlight_index

        self.annotations = annotations if annotations else []

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
        if self.is_drawing_mode and event.button() == Qt.LeftButton:
            # Start drawing
            self.is_currently_drawing = True
            self.current_drawing_points = [(event.pos().x() / self.zoom_level, 
                                            event.pos().y() / self.zoom_level)]
            self.update()
        else:
            # Normal text selection
            self.input_handler.handle_page_label_mouse_press(self, event)

    def mouseMoveEvent(self, event):
        if self.is_drawing_mode and self.is_currently_drawing:
            # Add point to current drawing
            self.current_drawing_points.append((event.pos().x() / self.zoom_level, 
                                            event.pos().y() / self.zoom_level))
            self.update()
        else:
            # Normal text selection
            self.input_handler.handle_page_label_mouse_move(self, event)
            
    def mouseReleaseEvent(self, event):
        if self.is_drawing_mode and event.button() == Qt.LeftButton and self.is_currently_drawing:
            # Finish drawing
            self.is_currently_drawing = False
            self.current_drawing_points.append((event.pos().x() / self.zoom_level, 
                                            event.pos().y() / self.zoom_level))
            
            # Create annotation from the drawn shape
            self._finalize_drawing()
            
            self.current_drawing_points = []
            self.update()
        else:
            # Normal text selection
            self.input_handler.handle_page_label_mouse_release(self, event)

    def _finalize_drawing(self):
        """Create an annotation from the current drawing."""
        if len(self.current_drawing_points) < 2:
            return  # Need at least 2 points
        
        # Emit signal to parent to create annotation
        # We'll handle this through the main window
        from helpers.annotations import Annotation
        
        # Get the main window through parent chain
        main_window = self.parent()
        while main_window and not hasattr(main_window, 'annotation_manager'):
            main_window = main_window.parent()
        
        if main_window:
            # Find which page this label represents
            page_index = None
            for idx, label in main_window.loaded_pages.items():
                if label == self:
                    page_index = idx
                    break
            
            if page_index is not None:
                annotation = Annotation(
                    page_index=page_index,
                    annotation_type=self.current_drawing_tool,
                    color=self.current_drawing_color,
                    points=self.current_drawing_points.copy(),
                    stroke_width=self.current_drawing_stroke_width,
                    filled=self.current_drawing_filled
                )
                main_window.annotation_manager.add_annotation(annotation)
                
                # Refresh this page to show the new annotation
                main_window._refresh_current_page()

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

        # --- NEW: Draw Annotations onto the buffer ---
        
        for annotation in self.annotations:
            
            # Set color based on annotation color (with some transparency)
            color = QColor(annotation.color[0], annotation.color[1], annotation.color[2], 100)
            
            if annotation.annotation_type == AnnotationType.HIGHLIGHT:
                # Draw highlight as filled rectangles
                buf_painter.setBrush(QBrush(color))
                for i, quad in enumerate(annotation.quads):
                    # Quads are [x0, y0, x1, y1, x2, y2, x3, y3]
                    # (x0,y0) = top-left, (x1,y1) = top-right
                    # (x2,y2) = bottom-left, (x3,y3) = bottom-right
                    rect = QRectF(
                        quad[0] * self.zoom_level,  # x0 (left)
                        quad[1] * self.zoom_level,  # y0 (top)
                        (quad[2] - quad[0]) * self.zoom_level,  # width: x1 - x0
                        (quad[5] - quad[1]) * self.zoom_level   # height: y2 - y0
                    )
                    buf_painter.drawRect(rect)

            elif annotation.annotation_type == AnnotationType.UNDERLINE:
                # Draw underline as a line at the bottom of the text
                buf_painter.setPen(color)
                for i, quad in enumerate(annotation.quads):
                    # Draw line from bottom-left to bottom-right
                    line_y = quad[5] * self.zoom_level  # y2 (bottom-left y coordinate)
                    buf_painter.drawLine(
                        int(quad[0] * self.zoom_level),  # x0 (left)
                        int(line_y),
                        int(quad[2] * self.zoom_level),  # x1 (right)
                        int(line_y)
                    )
                buf_painter.setPen(Qt.NoPen)

        # --- Draw Text Selection Highlights onto the buffer ---

        if self.selection_rects:
            # Choose color for the text selection highlights
            if self.dark_mode:
                selection_color = QColor(255, 255, 0, 100) # Yellow (dark mode)
            else:
                selection_color = QColor(0, 89, 195, 100) # Blue (light mode)
                
            buf_painter.setBrush(QBrush(selection_color))
            
            for rect in self.selection_rects:
                buf_painter.drawRect(rect) 
        
        buf_painter.end()

        # --- Draw current drawing in progress (real-time preview) ---

        if self.is_currently_drawing and len(self.current_drawing_points) >= 2:
            preview_color = QColor(self.current_drawing_color[0], 
                                self.current_drawing_color[1], 
                                self.current_drawing_color[2], 150)
            
            pen = QPen(preview_color, self.current_drawing_stroke_width)
            buf_painter.setPen(pen)
            
            if self.current_drawing_tool == AnnotationType.FREEHAND:
                # Draw freehand path
                if self.current_drawing_filled:
                    buf_painter.setBrush(QBrush(preview_color))
                path = QPainterPath()
                first_point = self.current_drawing_points[0]
                path.moveTo(first_point[0] * self.zoom_level, first_point[1] * self.zoom_level)
                for point in self.current_drawing_points[1:]:
                    path.lineTo(point[0] * self.zoom_level, point[1] * self.zoom_level)
                buf_painter.drawPath(path)
                buf_painter.setBrush(Qt.NoBrush)
            
            elif self.current_drawing_tool == AnnotationType.LINE:
                # Draw line from first to last point
                start = self.current_drawing_points[0]
                end = self.current_drawing_points[-1]
                buf_painter.drawLine(
                    int(start[0] * self.zoom_level), int(start[1] * self.zoom_level),
                    int(end[0] * self.zoom_level), int(end[1] * self.zoom_level)
                )
            
            elif self.current_drawing_tool == AnnotationType.ARROW:
                # Draw arrow from first to last point
                start = self.current_drawing_points[0]
                end = self.current_drawing_points[-1]
                
                # Draw main line
                buf_painter.drawLine(
                    int(start[0] * self.zoom_level), int(start[1] * self.zoom_level),
                    int(end[0] * self.zoom_level), int(end[1] * self.zoom_level)
                )
                
                # Draw arrowhead
                arrow_size = 10 * (self.current_drawing_stroke_width / 2.0)
                dx = end[0] - start[0]
                dy = end[1] - start[1]
                angle = math.atan2(dy, dx)
                
                arrow_p1 = QPointF(
                    end[0] * self.zoom_level - arrow_size * math.cos(angle - math.pi / 6),
                    end[1] * self.zoom_level - arrow_size * math.sin(angle - math.pi / 6)
                )
                arrow_p2 = QPointF(
                    end[0] * self.zoom_level - arrow_size * math.cos(angle + math.pi / 6),
                    end[1] * self.zoom_level - arrow_size * math.sin(angle + math.pi / 6)
                )
                
                buf_painter.drawLine(QPointF(end[0] * self.zoom_level, end[1] * self.zoom_level), arrow_p1)
                buf_painter.drawLine(QPointF(end[0] * self.zoom_level, end[1] * self.zoom_level), arrow_p2)
            
            elif self.current_drawing_tool == AnnotationType.RECTANGLE:
                # Draw rectangle from first to last point
                start = self.current_drawing_points[0]
                end = self.current_drawing_points[-1]
                
                x = min(start[0], end[0]) * self.zoom_level
                y = min(start[1], end[1]) * self.zoom_level
                width = abs(end[0] - start[0]) * self.zoom_level
                height = abs(end[1] - start[1]) * self.zoom_level
                
                if self.current_drawing_filled:
                    buf_painter.setBrush(QBrush(preview_color))
                buf_painter.drawRect(QRectF(x, y, width, height))
                buf_painter.setBrush(Qt.NoBrush)
            
            elif self.current_drawing_tool == AnnotationType.CIRCLE:
                # Draw circle/ellipse from first to last point
                start = self.current_drawing_points[0]
                end = self.current_drawing_points[-1]
                
                x = min(start[0], end[0]) * self.zoom_level
                y = min(start[1], end[1]) * self.zoom_level
                width = abs(end[0] - start[0]) * self.zoom_level
                height = abs(end[1] - start[1]) * self.zoom_level
                
                if self.current_drawing_filled:
                    buf_painter.setBrush(QBrush(preview_color))
                buf_painter.drawEllipse(QRectF(x, y, width, height))
                buf_painter.setBrush(Qt.NoBrush)
            
            buf_painter.setPen(Qt.NoPen)

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
    
    def set_drawing_mode(self, enabled, tool=None, color=None, stroke_width=None, filled=None):
        """Enable or disable drawing mode and update tool settings."""
        self.is_drawing_mode = enabled
        
        if tool is not None:
            self.current_drawing_tool = tool
        if color is not None:
            self.current_drawing_color = color
        if stroke_width is not None:
            self.current_drawing_stroke_width = stroke_width
        if filled is not None:
            self.current_drawing_filled = filled
        
        # Change cursor when in drawing mode
        if self.is_drawing_mode:
            self.setCursor(Qt.CrossCursor)
        else:
            self.setCursor(Qt.ArrowCursor)

    

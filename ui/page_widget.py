from PyQt5.QtCore import Qt, QRectF, QPointF, pyqtSignal
from PyQt5.QtGui import QPainter, QColor, QBrush, QPen, QFont, QCursor, QPixmap, QImage
from PyQt5.QtWidgets import QWidget
from typing import Optional, List, Tuple

class PageWidget(QWidget):
    """
    Hybrid page widget that uses PyMuPDF for accurate text rendering
    but keeps element extraction for selection and links.
    """
    
    # Signals
    link_clicked = pyqtSignal(str, object)  # link_type, destination
    text_selection_changed = pyqtSignal(str)  # selected text
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Page data
        self.page_elements = None
        self.page_pixmap = None  # Rendered page image
        self.page_index = 0
        self.zoom_level = 1.0
        self.dark_mode = False
        
        # Selection state
        self.selection_start_pos = None
        self.selection_end_pos = None
        self.selected_chars = []
        self.is_selecting = False
        
        # Hover state for links
        self.hovered_link = None
        
        # Search highlights
        self.search_highlights = []
        self.current_search_highlight_index = -1
        
        # Annotations
        self.annotations = []
        
        # Drawing state
        self.is_drawing_mode = False
        self.current_drawing_tool = None
        self.current_drawing_color = (255, 0, 0)
        self.current_drawing_stroke_width = 2.0
        self.current_drawing_filled = False
        self.current_drawing_points = []
        self.is_currently_drawing = False
        
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
    
    def set_page_data(self, page_pixmap, page_elements, page_index, zoom_level, dark_mode,
                     search_highlights=None, current_highlight_index=-1, annotations=None):
        """Set the page data and rendering parameters."""
        self.page_pixmap = page_pixmap
        self.page_elements = page_elements
        self.page_index = page_index
        self.zoom_level = zoom_level
        self.dark_mode = dark_mode
        
        self.search_highlights = search_highlights if search_highlights else []
        self.current_search_highlight_index = current_highlight_index
        self.annotations = annotations if annotations else []
        
        # Calculate widget size based on pixmap
        if page_pixmap:
            self.setMinimumSize(page_pixmap.width(), page_pixmap.height())
            self.setMaximumSize(page_pixmap.width(), page_pixmap.height())
        
        self.update()
    
    def paintEvent(self, event):
        """Custom paint event to render the page."""
        if not self.page_pixmap:
            return
        
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        
        # Draw the rendered page image
        painter.drawPixmap(0, 0, self.page_pixmap)
        
        # Now draw overlays (search highlights, selection, etc.)
        
        # 1. Render search highlights
        self._render_search_highlights(painter)
        
        # 2. Render annotations
        self._render_annotations(painter)
        
        # 3. Render text selection
        self._render_selection(painter)
        
        # 4. Render link highlights (on hover)
        self._render_link_highlight(painter)
        
        # 5. Render current drawing
        if self.is_currently_drawing:
            self._render_current_drawing(painter)
        
        painter.end()
    
    def _render_search_highlights(self, painter):
        """Render search result highlights."""
        if not self.search_highlights:
            return
        
        painter.setPen(Qt.NoPen)
        
        if self.dark_mode:
            highlight_color = QColor(255, 255, 0, 100)
            current_color = QColor(255, 255, 0, 150)
        else:
            highlight_color = QColor(255, 255, 0, 100)
            current_color = QColor(0, 89, 195, 100)
        
        for i, rect in enumerate(self.search_highlights):
            if i == self.current_search_highlight_index:
                painter.setBrush(QBrush(current_color))
            else:
                painter.setBrush(QBrush(highlight_color))
            
            scaled_rect = QRectF(
                rect.x0 * self.zoom_level,
                rect.y0 * self.zoom_level,
                rect.width * self.zoom_level,
                rect.height * self.zoom_level
            )
            painter.drawRect(scaled_rect)
    
    def _render_annotations(self, painter):
        """Render user annotations."""
        pass
    
    def _render_selection(self, painter):
        """Render text selection highlight."""
        if not self.selected_chars:
            return
        
        painter.setPen(Qt.NoPen)
        
        if self.dark_mode:
            selection_color = QColor(100, 150, 255, 80)
        else:
            selection_color = QColor(0, 120, 215, 80)
        
        painter.setBrush(QBrush(selection_color))
        
        # Draw selection rectangles for each selected character
        for char, bbox in self.selected_chars:
            scaled_rect = QRectF(
                bbox[0] * self.zoom_level,
                bbox[1] * self.zoom_level,
                (bbox[2] - bbox[0]) * self.zoom_level,
                (bbox[3] - bbox[1]) * self.zoom_level
            )
            painter.drawRect(scaled_rect)
    
    def _render_link_highlight(self, painter):
        """Render highlight for hovered link."""
        if not self.hovered_link:
            return
        
        painter.setPen(QPen(QColor(0, 120, 215), 1))
        painter.setBrush(QBrush(QColor(0, 120, 215, 30)))
        
        bbox = self.hovered_link.bbox
        scaled_rect = QRectF(
            bbox[0] * self.zoom_level,
            bbox[1] * self.zoom_level,
            (bbox[2] - bbox[0]) * self.zoom_level,
            (bbox[3] - bbox[1]) * self.zoom_level
        )
        painter.drawRect(scaled_rect)
    
    def _render_current_drawing(self, painter):
        """Render the drawing being created in real-time."""
        pass
    
    def mousePressEvent(self, event):
        """Handle mouse press for text selection and link clicking."""
        if event.button() == Qt.LeftButton:
            pos_in_page = self._screen_to_page_coords(event.pos())
            
            # Check if clicking on a link
            if self.hovered_link and not self.is_drawing_mode:
                self.link_clicked.emit(self.hovered_link.link_type, self.hovered_link.destination)
                return
            
            if self.is_drawing_mode:
                self.is_currently_drawing = True
                self.current_drawing_points = [pos_in_page]
            else:
                self.is_selecting = True
                self.selection_start_pos = pos_in_page
                self.selection_end_pos = pos_in_page
                self._update_selection()
    
    def mouseMoveEvent(self, event):
        """Handle mouse move for selection and link hovering."""
        pos_in_page = self._screen_to_page_coords(event.pos())
        
        if self.is_selecting and event.buttons() & Qt.LeftButton:
            self.selection_end_pos = pos_in_page
            self._update_selection()
            self.update()
        
        elif self.is_currently_drawing:
            self.current_drawing_points.append(pos_in_page)
            self.update()
        
        else:
            self._update_hover_state(pos_in_page)
    
    def mouseReleaseEvent(self, event):
        """Handle mouse release."""
        if event.button() == Qt.LeftButton:
            if self.is_selecting:
                self.is_selecting = False
                text = self._get_selected_text()
                self.text_selection_changed.emit(text)
            
            elif self.is_currently_drawing:
                self.is_currently_drawing = False
    
    def _screen_to_page_coords(self, screen_pos):
        """Convert screen coordinates to page coordinates."""
        return (
            screen_pos.x() / self.zoom_level,
            screen_pos.y() / self.zoom_level
        )
    
    def _update_selection(self):
        """Update selected characters based on selection rectangle."""
        if not self.page_elements or not self.selection_start_pos or not self.selection_end_pos:
            return
        
        # Create selection rectangle
        x0 = min(self.selection_start_pos[0], self.selection_end_pos[0])
        y0 = min(self.selection_start_pos[1], self.selection_end_pos[1])
        x1 = max(self.selection_start_pos[0], self.selection_end_pos[0])
        y1 = max(self.selection_start_pos[1], self.selection_end_pos[1])
        
        # Find all characters within selection from all text spans
        self.selected_chars = []
        for text_elem in self.page_elements.texts:
            for char, bbox in text_elem.chars:
                # Check if ANY part of the character bbox intersects with selection
                char_x0, char_y0, char_x1, char_y1 = bbox
                
                # Check for intersection
                intersects = not (char_x1 < x0 or char_x0 > x1 or char_y1 < y0 or char_y0 > y1)
                
                if intersects:
                    # Additional check: at least 30% of character width should be selected
                    overlap_x0 = max(char_x0, x0)
                    overlap_x1 = min(char_x1, x1)
                    overlap_width = overlap_x1 - overlap_x0
                    char_width = char_x1 - char_x0
                    
                    if char_width > 0 and overlap_width / char_width >= 0.3:
                        self.selected_chars.append((char, bbox))
    
    def _get_selected_text(self) -> str:
        """Get the selected text as a string."""
        if not self.selected_chars:
            return ""
        
        # Sort by position (top to bottom, left to right)
        sorted_chars = sorted(self.selected_chars, key=lambda t: (t[1][1], t[1][0]))
        
        # Reconstruct text with line breaks and spaces
        result = []
        last_y = None
        last_x = None
        last_bbox = None
        
        for char, bbox in sorted_chars:
            # Check for new line (vertical gap)
            if last_y is not None:
                y_diff = abs(bbox[1] - last_y)
                # New line if Y position changes significantly
                if y_diff > 3:
                    result.append('\n')
                    last_x = None  # Reset horizontal tracking
                # Check for horizontal gap (space between words)
                elif last_x is not None and last_bbox is not None:
                    # Calculate gap between last character's end and current character's start
                    gap = bbox[0] - last_x
                    # Average character width from last character
                    last_char_width = last_bbox[2] - last_bbox[0]
                    # If gap is larger than 30% of character width, add space
                    if gap > last_char_width * 0.3:
                        result.append(' ')
            
            result.append(char)
            last_y = bbox[1]
            last_x = bbox[2]  # Right edge of current character
            last_bbox = bbox
        
        return ''.join(result)
    
    def _update_hover_state(self, pos_in_page):
        """Update link hover state."""
        if not self.page_elements:
            return
        
        old_hovered_link = self.hovered_link
        self.hovered_link = None
        
        for link in self.page_elements.links:
            bbox = link.bbox
            if bbox[0] <= pos_in_page[0] <= bbox[2] and bbox[1] <= pos_in_page[1] <= bbox[3]:
                self.hovered_link = link
                break
        
        if self.hovered_link:
            self.setCursor(QCursor(Qt.PointingHandCursor))
        else:
            self.setCursor(QCursor(Qt.IBeamCursor if not self.is_drawing_mode else Qt.CrossCursor))
        
        if old_hovered_link != self.hovered_link:
            self.update()
    
    def clear_selection(self):
        """Clear the current text selection."""
        self.selected_chars = []
        self.selection_start_pos = None
        self.selection_end_pos = None
        self.update()
    
    def set_drawing_mode(self, enabled, tool=None, color=None, stroke_width=None, filled=None):
        """Enable or disable drawing mode."""
        self.is_drawing_mode = enabled
        
        if tool is not None:
            self.current_drawing_tool = tool
        if color is not None:
            self.current_drawing_color = color
        if stroke_width is not None:
            self.current_drawing_stroke_width = stroke_width
        if filled is not None:
            self.current_drawing_filled = filled
        
        if self.is_drawing_mode:
            self.setCursor(QCursor(Qt.CrossCursor))
        else:
            self.setCursor(QCursor(Qt.IBeamCursor))
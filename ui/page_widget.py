from PyQt5.QtCore import Qt, QRectF, QPointF, pyqtSignal
from PyQt5.QtGui import QPainter, QColor, QBrush, QPen, QFont, QCursor
from PyQt5.QtWidgets import QWidget
from typing import Optional, List, Tuple

class PageWidget(QWidget):
    """
    Page widget that renders PDF elements individually.
    """
    
    # Signals
    link_clicked = pyqtSignal(str, object)  # link_type, destination
    text_selection_changed = pyqtSignal(str)  # selected text
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Page data
        self.page_elements = None
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
    
    def set_page_data(self, page_elements, page_index, zoom_level, dark_mode,
                     search_highlights=None, current_highlight_index=-1, annotations=None):
        """Set the page data and rendering parameters."""
        self.page_elements = page_elements
        self.page_index = page_index
        self.zoom_level = zoom_level
        self.dark_mode = dark_mode
        
        self.search_highlights = search_highlights if search_highlights else []
        self.current_search_highlight_index = current_highlight_index
        self.annotations = annotations if annotations else []
        
        # Calculate widget size based on page dimensions
        if page_elements:
            width = int(page_elements.width * zoom_level)
            height = int(page_elements.height * zoom_level)
            self.setMinimumSize(width, height)
            self.setMaximumSize(width, height)
        
        self.update()
    
    def paintEvent(self, event):
        """Custom paint event to render PDF elements."""
        if not self.page_elements:
            return
        
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.TextAntialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        
        # Fill page background with appropriate color
        if self.dark_mode:
            page_bg_color = QColor(50, 50, 50)  # Slightly lighter than app background
        else:
            page_bg_color = QColor(255, 255, 255)
        
        painter.fillRect(self.rect(), page_bg_color)
        
        # Add subtle border/shadow effect
        border_pen = QPen(QColor(0, 0, 0, 30) if not self.dark_mode else QColor(0, 0, 0, 60))
        border_pen.setWidth(1)
        painter.setPen(border_pen)
        painter.drawRect(self.rect().adjusted(0, 0, -1, -1))
        
        # Save painter state
        painter.save()
        
        # Apply zoom transformation
        painter.scale(self.zoom_level, self.zoom_level)
        
        # Render in order: vectors -> images -> text
        
        # 1. Render vector elements (background shapes, lines)
        self._render_vectors(painter)
        
        # 2. Render images
        self._render_images(painter)
        
        # 3. Render text
        self._render_text(painter)
        
        # Restore painter state for overlays
        painter.restore()
        
        # 4. Render search highlights (in screen coordinates)
        self._render_search_highlights(painter)
        
        # 5. Render annotations
        self._render_annotations(painter)
        
        # 6. Render text selection
        self._render_selection(painter)
        
        # 7. Render link highlights (on hover)
        self._render_link_highlight(painter)
        
        # 8. Render current drawing
        if self.is_currently_drawing:
            self._render_current_drawing(painter)
        
        painter.end()
    
    def _render_vectors(self, painter):
        """Render vector graphics."""
        if not self.page_elements:
            return
        
        for vector in self.page_elements.vectors:
            # Set colors based on dark mode
            if vector.fill_color:
                if self.dark_mode:
                    fill_color = QColor(
                        255 - vector.fill_color[0],
                        255 - vector.fill_color[1],
                        255 - vector.fill_color[2]
                    )
                else:
                    fill_color = QColor(*vector.fill_color)
                painter.fillPath(vector.path, QBrush(fill_color))
            
            if vector.stroke_color:
                if self.dark_mode:
                    stroke_color = QColor(
                        255 - vector.stroke_color[0],
                        255 - vector.stroke_color[1],
                        255 - vector.stroke_color[2]
                    )
                else:
                    stroke_color = QColor(*vector.stroke_color)
                
                pen = QPen(stroke_color)
                pen.setWidthF(vector.line_width)
                painter.setPen(pen)
                painter.drawPath(vector.path)
    
    def _render_images(self, painter):
        """Render embedded images."""
        if not self.page_elements:
            return
        
        for image in self.page_elements.images:
            bbox = image.bbox
            target_rect = QRectF(bbox[0], bbox[1], bbox[2] - bbox[0], bbox[3] - bbox[1])
            
            pixmap = image.pixmap
            if self.dark_mode:
                img = pixmap.toImage()
                img.invertPixels()
                pixmap = pixmap.fromImage(img)
            
            painter.drawPixmap(target_rect, pixmap, QRectF(pixmap.rect()))
    
    def _render_text(self, painter):
        """Render text spans at their exact positions."""
        if not self.page_elements:
            return
        
        for text_elem in self.page_elements.texts:
            # Set font - convert PDF points to screen pixels
            # PDF uses points (1/72 inch), Qt uses pixels
            font = QFont(text_elem.font_name)
            # Use the exact font size from PDF without any scaling
            font.setPixelSize(int(text_elem.font_size))
            painter.setFont(font)
            
            # Set color (with smart dark mode inversion)
            if self.dark_mode:
                brightness = sum(text_elem.color) / 3
                if brightness < 128:
                    # Invert dark text
                    color = QColor(
                        255 - text_elem.color[0],
                        255 - text_elem.color[1],
                        255 - text_elem.color[2]
                    )
                else:
                    # Keep light text
                    color = QColor(*text_elem.color)
            else:
                color = QColor(*text_elem.color)
            
            painter.setPen(color)
            
            # Draw text at baseline position (bottom-left of bbox)
            bbox = text_elem.bbox
            painter.drawText(
                QPointF(bbox[0], bbox[3]),
                text_elem.text
            )
    
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
                # This is more accurate than just checking the center
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
        
        # Reconstruct text with line breaks
        result = []
        last_y = None
        last_x = None
        
        for char, bbox in sorted_chars:
            # Check for new line
            if last_y is not None:
                y_diff = abs(bbox[1] - last_y)
                # Use a smaller threshold for more accurate line detection
                if y_diff > 5:  # More than 5 points difference = new line
                    result.append('\n')
                # Check for significant horizontal gap (likely a space)
                elif last_x is not None:
                    x_gap = bbox[0] - last_x
                    # If gap is larger than typical character width, add space
                    if x_gap > (bbox[2] - bbox[0]) * 0.5:
                        result.append(' ')
            
            result.append(char)
            last_y = bbox[1]
            last_x = bbox[2]
        
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
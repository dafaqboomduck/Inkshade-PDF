from PyQt5.QtCore import Qt, QRectF, QPointF, pyqtSignal
from PyQt5.QtGui import QPainter, QColor, QBrush, QPen, QFont, QCursor
from PyQt5.QtWidgets import QWidget
from typing import Optional, List, Tuple

class PageWidget(QWidget):
    """
    Enhanced page widget that renders PDF elements individually
    instead of as a rasterized image.
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
        
        # Render in order: vectors -> images -> text -> highlights -> selection
        
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
                    # Invert fill color for dark mode
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
                    # Invert stroke color for dark mode
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
                # Invert image colors for dark mode
                img = pixmap.toImage()
                img.invertPixels()
                pixmap = pixmap.fromImage(img)
            
            painter.drawPixmap(target_rect, pixmap, QRectF(pixmap.rect()))
    
    def _render_text(self, painter):
        """Render text characters using their original positions."""
        if not self.page_elements:
            return
        
        # Draw each character at its exact position
        for text_elem in self.page_elements.texts:
            # Set font
            font = QFont(text_elem.font_name)
            font.setPointSizeF(text_elem.font_size)
            painter.setFont(font)
            
            # Set color (with dark mode inversion)
            if self.dark_mode:
                # Check if color is very dark (likely text)
                brightness = sum(text_elem.color) / 3
                if brightness < 128:
                    # Invert dark colors
                    color = QColor(
                        255 - text_elem.color[0],
                        255 - text_elem.color[1],
                        255 - text_elem.color[2]
                    )
                else:
                    # Keep light colors as-is
                    color = QColor(*text_elem.color)
            else:
                color = QColor(*text_elem.color)
            
            painter.setPen(color)
            
            # Draw character at its baseline position
            # PDF uses baseline coordinates (bottom-left of character)
            bbox = text_elem.bbox
            painter.drawText(
                QPointF(bbox[0], bbox[3]),
                text_elem.char
            )
    
    def _render_search_highlights(self, painter):
        """Render search result highlights."""
        if not self.search_highlights:
            return
        
        painter.setPen(Qt.NoPen)
        
        # Highlight color based on dark mode
        if self.dark_mode:
            highlight_color = QColor(255, 255, 0, 100)
            current_color = QColor(255, 255, 0, 150)
        else:
            highlight_color = QColor(255, 255, 0, 100)
            current_color = QColor(0, 89, 195, 100)
        
        # Draw all highlights
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
        # Implementation similar to current page_label.py
        # This would use the annotation rendering code from your existing implementation
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
        
        # Group consecutive characters on same line
        for char_elem in self.selected_chars:
            bbox = char_elem.bbox
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
        # Similar to existing drawing rendering code
        pass
    
    def mousePressEvent(self, event):
        """Handle mouse press for text selection and link clicking."""
        if event.button() == Qt.LeftButton:
            pos_in_page = self._screen_to_page_coords(event.pos())
            
            # Check if clicking on a link
            if self.page_elements:
                from core.pdf_reader import PDFDocumentReader
                # This would need access to the PDF reader to check links
                # For now, just handle selection
                
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
            # Check for link hovering
            self._update_hover_state(pos_in_page)
    
    def mouseReleaseEvent(self, event):
        """Handle mouse release."""
        if event.button() == Qt.LeftButton:
            if self.is_selecting:
                self.is_selecting = False
                # Emit selected text
                text = self._get_selected_text()
                self.text_selection_changed.emit(text)
            
            elif self.is_currently_drawing:
                self.is_currently_drawing = False
                # Finalize drawing
                # This would create an annotation
    
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
        
        # Find all characters within selection
        self.selected_chars = []
        for text_elem in self.page_elements.texts:
            bbox = text_elem.bbox
            # Check if character center is within selection
            char_center_x = (bbox[0] + bbox[2]) / 2
            char_center_y = (bbox[1] + bbox[3]) / 2
            
            if x0 <= char_center_x <= x1 and y0 <= char_center_y <= y1:
                self.selected_chars.append(text_elem)
    
    def _get_selected_text(self) -> str:
        """Get the selected text as a string."""
        if not self.selected_chars:
            return ""
        
        # Sort by position (top to bottom, left to right)
        sorted_chars = sorted(self.selected_chars, key=lambda t: (t.bbox[1], t.bbox[0]))
        
        # Reconstruct text with line breaks
        result = []
        last_y = None
        
        for char in sorted_chars:
            if last_y is not None and abs(char.bbox[1] - last_y) > char.font_size * 0.5:
                result.append('\n')
            result.append(char.char)
            last_y = char.bbox[1]
        
        return ''.join(result)
    
    def _update_hover_state(self, pos_in_page):
        """Update link hover state."""
        if not self.page_elements:
            return
        
        # Check if hovering over a link
        old_hovered_link = self.hovered_link
        self.hovered_link = None
        
        for link in self.page_elements.links:
            bbox = link.bbox
            if bbox[0] <= pos_in_page[0] <= bbox[2] and bbox[1] <= pos_in_page[1] <= bbox[3]:
                self.hovered_link = link
                break
        
        # Update cursor
        if self.hovered_link:
            self.setCursor(QCursor(Qt.PointingHandCursor))
        else:
            self.setCursor(QCursor(Qt.IBeamCursor if not self.is_drawing_mode else Qt.CrossCursor))
        
        # Repaint if hover state changed
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
        
        # Update cursor
        if self.is_drawing_mode:
            self.setCursor(QCursor(Qt.CrossCursor))
        else:
            self.setCursor(QCursor(Qt.IBeamCursor))
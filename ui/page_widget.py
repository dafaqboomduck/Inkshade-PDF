from PyQt5.QtCore import Qt, QRectF, QPointF, pyqtSignal
from PyQt5.QtGui import (QPainter, QColor, QBrush, QPen, QFont, 
                         QCursor, QPixmap, QImage, QPainterPath)
from PyQt5.QtWidgets import QWidget, QApplication
from typing import Optional, List, Tuple
import math
import time

# Imports from your old file for annotations
from helpers.annotations import Annotation
from core.annotation_manager import AnnotationType

class PageWidget(QWidget):
    """
    Hybrid page widget that uses PyMuPDF for accurate text rendering
    and custom logic for text selection, links, and annotations.
    
    Includes modern selection logic (single, double, triple-click).
    """
    
    # Signals
    link_clicked = pyqtSignal(str, object)  # link_type, destination
    text_selection_changed = pyqtSignal(str)  # selected text
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Page data
        self.page_elements = None
        self.page_pixmap = None
        self.page_index = 0
        self.zoom_level = 1.0
        self.dark_mode = False
        
        # Selection state
        self.selection_start_index = None
        self.selection_end_index = None
        self.selected_chars = []
        self.is_selecting = False
        self._all_chars = []
        
        # --- NEW: Click-handling state ---
        self.last_press_time = 0
        self.last_double_click_time = 0
        
        # Hover state for links
        self.hovered_link = None
        
        # Search highlights
        self.search_highlights = []
        self.current_search_highlight_index = -1
        
        # Annotations
        self.annotations = []
        
        # Drawing state
        self.is_drawing_mode = False
        self.current_drawing_tool = AnnotationType.FREEHAND
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
        
        # --- NEW: Build augmented character list ---
        temp_chars = []
        if self.page_elements:
            for text_elem in self.page_elements.texts:
                for char, bbox in text_elem.chars:
                    temp_chars.append({'char': char, 'bbox': bbox})
        
        # Sort by reading order (top-to-bottom, left-to-right)
        temp_chars = sorted(temp_chars, key=lambda c: (c['bbox'][1], c['bbox'][0]))
        
        # Now, augment with line and word info
        self._all_chars = []
        current_line_index = 0
        current_word_index = 0
        last_y = -1
        last_x_end = -1
        
        for i, char_data in enumerate(temp_chars):
            bbox = char_data['bbox']
            char = char_data['char']
            
            # Check for new line
            if last_y != -1 and abs(bbox[1] - last_y) > 3: # y-pos changed significantly
                current_line_index += 1
                current_word_index += 1 # New line always means new word
            # Check for new word (space)
            elif last_x_end != -1 and (bbox[0] - last_x_end) > (bbox[2] - bbox[0]) * 0.3:
                current_word_index += 1
            
            # Add augmented data
            char_data['line_index'] = current_line_index
            char_data['word_index'] = current_word_index
            self._all_chars.append(char_data)
            
            # Update state
            last_y = bbox[1]
            last_x_end = bbox[2]
            
            # Don't let whitespace be the *start* of a new word index if it's trailing
            if char.isspace():
                current_word_index += 1
                
        self.clear_selection()
        self.update()
    
    def paintEvent(self, event):
        """Custom paint event to render the page."""
        if not self.page_pixmap:
            return
        
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        
        painter.drawPixmap(0, 0, self.page_pixmap)
        
        self._render_search_highlights(painter)
        self._render_annotations(painter)
        self._render_selection(painter)
        self._render_link_highlight(painter)
        
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
        for annotation in self.annotations:
            color = QColor(annotation.color[0], annotation.color[1], annotation.color[2], 100)
            
            if annotation.annotation_type == AnnotationType.HIGHLIGHT:
                painter.setBrush(QBrush(color))
                painter.setPen(Qt.NoPen)
                for quad in annotation.quads:
                    rect = QRectF(
                        quad[0] * self.zoom_level,
                        quad[1] * self.zoom_level,
                        (quad[2] - quad[0]) * self.zoom_level,
                        (quad[5] - quad[1]) * self.zoom_level
                    )
                    painter.drawRect(rect)
                painter.setBrush(Qt.NoBrush)
            
            elif annotation.annotation_type == AnnotationType.UNDERLINE:
                pen = QPen(color, 2)
                pen.setCapStyle(Qt.FlatCap)
                painter.setPen(pen)
                for quad in annotation.quads:
                    line_y = (quad[5] * self.zoom_level) + 1
                    painter.drawLine(
                        int(quad[0] * self.zoom_level),
                        int(line_y),
                        int(quad[2] * self.zoom_level),
                        int(line_y)
                    )
                painter.setPen(Qt.NoPen)
            
            elif annotation.annotation_type in [AnnotationType.FREEHAND, AnnotationType.LINE, 
                                                AnnotationType.ARROW, AnnotationType.RECTANGLE, 
                                                AnnotationType.CIRCLE]:
                
                if not annotation.points or len(annotation.points) < 2:
                    continue
                
                solid_color = QColor(annotation.color[0], annotation.color[1], annotation.color[2], 255)
                pen = QPen(solid_color, annotation.stroke_width)
                painter.setPen(pen)
                
                if annotation.annotation_type == AnnotationType.FREEHAND:
                    if annotation.filled:
                        painter.setBrush(QBrush(solid_color))
                    path = QPainterPath()
                    first_point = annotation.points[0]
                    path.moveTo(first_point[0] * self.zoom_level, first_point[1] * self.zoom_level)
                    for point in annotation.points[1:]:
                        path.lineTo(point[0] * self.zoom_level, point[1] * self.zoom_level)
                    painter.drawPath(path)
                    if annotation.filled:
                        painter.setBrush(Qt.NoBrush)
                
                elif annotation.annotation_type == AnnotationType.LINE:
                    start = annotation.points[0]
                    end = annotation.points[-1]
                    painter.drawLine(
                        int(start[0] * self.zoom_level), int(start[1] * self.zoom_level),
                        int(end[0] * self.zoom_level), int(end[1] * self.zoom_level)
                    )
                
                elif annotation.annotation_type == AnnotationType.ARROW:
                    start = annotation.points[0]
                    end = annotation.points[-1]
                    painter.drawLine(
                        int(start[0] * self.zoom_level), int(start[1] * self.zoom_level),
                        int(end[0] * self.zoom_level), int(end[1] * self.zoom_level)
                    )
                    arrow_size = 10 * (annotation.stroke_width / 2.0)
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
                    painter.drawLine(QPointF(end[0] * self.zoom_level, end[1] * self.zoom_level), arrow_p1)
                    painter.drawLine(QPointF(end[0] * self.zoom_level, end[1] * self.zoom_level), arrow_p2)
                
                elif annotation.annotation_type == AnnotationType.RECTANGLE:
                    start = annotation.points[0]
                    end = annotation.points[-1]
                    x = min(start[0], end[0]) * self.zoom_level
                    y = min(start[1], end[1]) * self.zoom_level
                    width = abs(end[0] - start[0]) * self.zoom_level
                    height = abs(end[1] - start[1]) * self.zoom_level
                    if annotation.filled:
                        painter.setBrush(QBrush(solid_color))
                    painter.drawRect(QRectF(x, y, width, height))
                    if annotation.filled:
                        painter.setBrush(Qt.NoBrush)
                
                elif annotation.annotation_type == AnnotationType.CIRCLE:
                    start = annotation.points[0]
                    end = annotation.points[-1]
                    x = min(start[0], end[0]) * self.zoom_level
                    y = min(start[1], end[1]) * self.zoom_level
                    width = abs(end[0] - start[0]) * self.zoom_level
                    height = abs(end[1] - start[1]) * self.zoom_level
                    if annotation.filled:
                        painter.setBrush(QBrush(solid_color))
                    painter.drawEllipse(QRectF(x, y, width, height))
                    if annotation.filled:
                        painter.setBrush(Qt.NoBrush)
                
                painter.setPen(Qt.NoPen)
    
    def _render_selection(self, painter):
        """Render text selection highlight."""
        if not self.selected_chars:
            return
        
        painter.setPen(Qt.NoPen)
        selection_color = QColor(0, 120, 215, 80)
        if self.dark_mode:
            selection_color = QColor(100, 150, 255, 80)
        
        painter.setBrush(QBrush(selection_color))
        
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
        if not self.is_currently_drawing or len(self.current_drawing_points) < 2:
            return
            
        preview_color = QColor(self.current_drawing_color[0], 
                               self.current_drawing_color[1], 
                               self.current_drawing_color[2], 150)
        
        pen = QPen(preview_color, self.current_drawing_stroke_width)
        painter.setPen(pen)
        
        if self.current_drawing_tool == AnnotationType.FREEHAND:
            if self.current_drawing_filled:
                painter.setBrush(QBrush(preview_color))
            path = QPainterPath()
            first_point = self.current_drawing_points[0]
            path.moveTo(first_point[0] * self.zoom_level, first_point[1] * self.zoom_level)
            for point in self.current_drawing_points[1:]:
                path.lineTo(point[0] * self.zoom_level, point[1] * self.zoom_level)
            painter.drawPath(path)
            if self.current_drawing_filled:
                painter.setBrush(Qt.NoBrush)
        
        elif self.current_drawing_tool == AnnotationType.LINE:
            start = self.current_drawing_points[0]
            end = self.current_drawing_points[-1]
            painter.drawLine(
                int(start[0] * self.zoom_level), int(start[1] * self.zoom_level),
                int(end[0] * self.zoom_level), int(end[1] * self.zoom_level)
            )
        
        elif self.current_drawing_tool == AnnotationType.ARROW:
            start = self.current_drawing_points[0]
            end = self.current_drawing_points[-1]
            
            painter.drawLine(
                int(start[0] * self.zoom_level), int(start[1] * self.zoom_level),
                int(end[0] * self.zoom_level), int(end[1] * self.zoom_level)
            )
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
            painter.drawLine(QPointF(end[0] * self.zoom_level, end[1] * self.zoom_level), arrow_p1)
            painter.drawLine(QPointF(end[0] * self.zoom_level, end[1] * self.zoom_level), arrow_p2)
        
        elif self.current_drawing_tool == AnnotationType.RECTANGLE:
            start = self.current_drawing_points[0]
            end = self.current_drawing_points[-1]
            x = min(start[0], end[0]) * self.zoom_level
            y = min(start[1], end[1]) * self.zoom_level
            width = abs(end[0] - start[0]) * self.zoom_level
            height = abs(end[1] - start[1]) * self.zoom_level
            if self.current_drawing_filled:
                painter.setBrush(QBrush(preview_color))
            painter.drawRect(QRectF(x, y, width, height))
            if self.current_drawing_filled:
                painter.setBrush(Qt.NoBrush)
        
        elif self.current_drawing_tool == AnnotationType.CIRCLE:
            start = self.current_drawing_points[0]
            end = self.current_drawing_points[-1]
            x = min(start[0], end[0]) * self.zoom_level
            y = min(start[1], end[1]) * self.zoom_level
            width = abs(end[0] - start[0]) * self.zoom_level
            height = abs(end[1] - start[1]) * self.zoom_level
            if self.current_drawing_filled:
                painter.setBrush(QBrush(preview_color))
            painter.drawEllipse(QRectF(x, y, width, height))
            if self.current_drawing_filled:
                painter.setBrush(Qt.NoBrush)
        
        painter.setPen(Qt.NoPen)
    
    # --- NEW: mouseDoubleClickEvent ---
    def mouseDoubleClickEvent(self, event):
        """Handle double-clicks to select a word."""
        self.last_double_click_time = time.time() # Log time for triple-click
        
        if self.is_drawing_mode or event.button() != Qt.LeftButton:
            return
            
        pos_in_page = self._screen_to_page_coords(event.pos())
        char_index = self._get_char_index_at_pos(pos_in_page)
        
        if char_index is not None:
            self._select_word_at_index(char_index)
            self.is_selecting = False # Don't start a drag
            self.text_selection_changed.emit(self._get_selected_text())
    
    # --- MODIFIED: mousePressEvent ---
    def mousePressEvent(self, event):
        """Handle single-clicks (drag) and triple-clicks (line)."""
        if event.button() == Qt.LeftButton:
            
            # 1. Handle Drawing
            if self.is_drawing_mode:
                self.is_currently_drawing = True
                self.current_drawing_points = [self._screen_to_page_coords(event.pos())]
                self.update()
                return
            
            # 2. Handle Link Clicking
            if self.hovered_link:
                self.link_clicked.emit(self.hovered_link.link_type, self.hovered_link.destination)
                return
            
            # --- NEW: Handle Triple-Click Logic ---
            current_time = time.time()
            double_click_interval = QApplication.instance().doubleClickInterval() / 1000.0
            
            # Check if this press is fast enough after a double-click
            if (current_time - self.last_double_click_time) < double_click_interval:
                # This is a triple click!
                self.last_double_click_time = 0 # Reset timer
                
                pos_in_page = self._screen_to_page_coords(event.pos())
                char_index = self._get_char_index_at_pos(pos_in_page)
                
                if char_index is not None:
                    self._select_line_at_index(char_index)
                    self.is_selecting = False # Don't start drag
                    self.text_selection_changed.emit(self._get_selected_text())
                return

            # --- MODIFIED: Handle Single-Click Logic ---
            
            # Log press time for future double-click check
            self.last_press_time = time.time()
            
            pos_in_page = self._screen_to_page_coords(event.pos())
            char_index = self._get_char_index_at_pos(pos_in_page)
            
            # Click on blank space: deselect
            if char_index is None:
                self.clear_selection()
                self.text_selection_changed.emit("")
                self.is_selecting = False
                return
            
            # Click on existing selection: deselect and start new selection
            is_on_selection = False
            if self.selection_start_index is not None:
                 is_on_selection = (min(self.selection_start_index, self.selection_end_index) <= char_index <= 
                                    max(self.selection_start_index, self.selection_end_index))
            
            if is_on_selection:
                self.clear_selection()
            
            # Standard single click: Start drag selection
            self.is_selecting = True
            self.selection_start_index = char_index
            self.selection_end_index = None  # Don't set end index yet
    
    def mouseMoveEvent(self, event):
        """Handle mouse move for selection, link hovering, OR drawing."""
        pos_in_page = self._screen_to_page_coords(event.pos())
        
        # 1. Handle Drawing
        if self.is_drawing_mode and self.is_currently_drawing:
            self.current_drawing_points.append(pos_in_page)
            self.update()
            return
        
        # 2. Handle Text Selection Drag
        if self.is_selecting and event.buttons() & Qt.LeftButton:
            char_index = self._get_char_index_at_pos(pos_in_page)
            if char_index is not None:
                # Only update selection if we've actually moved to a different character
                if self.selection_end_index is None or self.selection_end_index != char_index:
                    self.selection_end_index = char_index
                    self._update_selection()
                    self.update()
        
        # 3. Handle Link Hovering
        elif not self.is_selecting:
            self._update_hover_state(pos_in_page)
    
    def mouseReleaseEvent(self, event):
        """Handle mouse release for selection OR drawing."""
        if event.button() == Qt.LeftButton:
            
            # 1. Handle Drawing
            if self.is_drawing_mode and self.is_currently_drawing:
                self.is_currently_drawing = False
                pos_in_page = self._screen_to_page_coords(event.pos())
                self.current_drawing_points.append(pos_in_page)
                
                self._finalize_drawing()
                
                self.current_drawing_points = []
                self.update()
                return
            
            # 2. Handle Text Selection
            if self.is_selecting:
                self.is_selecting = False
                text = self._get_selected_text()
                self.text_selection_changed.emit(text)
    
    def _screen_to_page_coords(self, screen_pos):
        """Convert screen coordinates to page coordinates."""
        return (
            screen_pos.x() / self.zoom_level,
            screen_pos.y() / self.zoom_level
        )
    
    # --- MODIFIED: _get_char_index_at_pos ---
    def _get_char_index_at_pos(self, pos_in_page):
        """
        Find the index of the character closest to the given page coordinates.
        Returns None if the click is on "blank space".
        """
        x_pos, y_pos = pos_in_page
        
        if not self._all_chars:
            return None
        
        min_dist_sq = float('inf')
        closest_index = 0
        
        for i, char_data in enumerate(self._all_chars):
            bbox = char_data['bbox']
            center_x = (bbox[0] + bbox[2]) / 2
            center_y = (bbox[1] + bbox[3]) / 2
            dist_sq = (x_pos - center_x)**2 + (y_pos - center_y)**2
            
            if dist_sq < min_dist_sq:
                min_dist_sq = dist_sq
                closest_index = i
        
        # --- NEW: Blank space check ---
        # Heuristic: If the click is further than ~1.5x the char's
        # dimensions away, consider it "blank space".
        closest_bbox = self._all_chars[closest_index]['bbox']
        char_width = closest_bbox[2] - closest_bbox[0]
        char_height = closest_bbox[3] - closest_bbox[1]
        max_allowed_dist = max(char_width, char_height) * 1.5
        
        if min_dist_sq > max_allowed_dist**2:
            return None # Click is too far from the closest char
            
        return closest_index

    # --- NEW: Helper for word selection ---
    def _select_word_at_index(self, index):
        """Selects all characters belonging to the same word as the char at `index`."""
        if index is None or not self._all_chars:
            return
            
        target_word_index = self._all_chars[index]['word_index']
        target_line_index = self._all_chars[index]['line_index']
        
        # Find start of the word
        start_idx = index
        while (start_idx > 0 and 
               self._all_chars[start_idx - 1]['word_index'] == target_word_index and
               self._all_chars[start_idx - 1]['line_index'] == target_line_index): # Stay on the same line
            start_idx -= 1
            
        # Find end of the word
        end_idx = index
        while (end_idx < len(self._all_chars) - 1 and 
               self._all_chars[end_idx + 1]['word_index'] == target_word_index and
               self._all_chars[end_idx + 1]['line_index'] == target_line_index): # Stay on the same line
            end_idx += 1
            
        self.selection_start_index = start_idx
        self.selection_end_index = end_idx
        self._update_selection()
        self.update()

    # --- NEW: Helper for line selection ---
    def _select_line_at_index(self, index):
        """Selects all characters belonging to the same line as the char at `index`."""
        if index is None or not self._all_chars:
            return
            
        target_line_index = self._all_chars[index]['line_index']
        
        # Find start of the line
        start_idx = index
        while (start_idx > 0 and 
               self._all_chars[start_idx - 1]['line_index'] == target_line_index):
            start_idx -= 1
            
        # Find end of the line
        end_idx = index
        while (end_idx < len(self._all_chars) - 1 and 
               self._all_chars[end_idx + 1]['line_index'] == target_line_index):
            end_idx += 1
            
        self.selection_start_index = start_idx
        self.selection_end_index = end_idx
        self._update_selection()
        self.update()

    def _update_selection(self):
        """Update selected characters based on start and end indices."""
        self.selected_chars = []
        
        if (self.selection_start_index is None or 
            self.selection_end_index is None or 
            not self._all_chars):
            return
        
        start_idx = min(self.selection_start_index, self.selection_end_index)
        end_idx = max(self.selection_start_index, self.selection_end_index)
        
        if start_idx == -1 or end_idx == -1:
            return
            
        for i in range(start_idx, end_idx + 1):
            char_data = self._all_chars[i]
            self.selected_chars.append((char_data['char'], char_data['bbox']))
    
    def _get_selected_text(self) -> str:
        """Get the selected text as a string."""
        if not self.selected_chars:
            return ""
        
        result = []
        last_y = None
        last_x = None
        last_bbox = None
        
        for char, bbox in self.selected_chars:
            if last_y is not None:
                y_diff = abs(bbox[1] - last_y)
                if y_diff > 3:
                    result.append('\n')
                    last_x = None
                elif last_x is not None and last_bbox is not None:
                    gap = bbox[0] - last_x
                    last_char_width = last_bbox[2] - last_bbox[0]
                    if gap > last_char_width * 0.3:
                        result.append(' ')
            
            result.append(char)
            last_y = bbox[1]
            last_x = bbox[2]
            last_bbox = bbox
        
        return ''.join(result)
    
    def _update_hover_state(self, pos_in_page):
        """Update link hover state."""
        if not self.page_elements or self.is_selecting:
            return
        
        old_hovered_link = self.hovered_link
        self.hovered_link = None
        
        for link in self.page_elements.links:
            bbox = link.bbox
            if bbox[0] <= pos_in_page[0] <= bbox[2] and bbox[1] <= pos_in_page[1] <= bbox[3]:
                self.hovered_link = link
                break
        
        cursor = QCursor(Qt.IBeamCursor if not self.is_drawing_mode else Qt.CrossCursor)
        if self.hovered_link:
            cursor = QCursor(Qt.PointingHandCursor)
        
        if self.cursor().shape() != cursor.shape():
            self.setCursor(cursor)
        
        if old_hovered_link != self.hovered_link:
            self.update()
    
    def _finalize_drawing(self):
        """Create an annotation from the current drawing."""
        if len(self.current_drawing_points) < 2:
            return
        
        main_window = self.parent()
        while main_window and not hasattr(main_window, 'annotation_manager'):
            main_window = main_window.parent()
        
        if main_window:
            page_index = self.page_index # We already know our index
            
            annotation = Annotation(
                page_index=page_index,
                annotation_type=self.current_drawing_tool,
                color=self.current_drawing_color,
                points=self.current_drawing_points.copy(),
                stroke_width=self.current_drawing_stroke_width,
                filled=self.current_drawing_filled
            )
            main_window.annotation_manager.add_annotation(annotation)
            main_window._refresh_current_page()
                
    def clear_selection(self):
        """Clear the current text selection."""
        self.selected_chars = []
        self.selection_start_index = None
        self.selection_end_index = None
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
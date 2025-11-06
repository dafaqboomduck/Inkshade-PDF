from PyQt5.QtCore import Qt, QRect, QRectF, QUrl, QPoint, QPointF
from PyQt5.QtGui import QPainter, QColor, QBrush, QImage, QDesktopServices, QCursor, QPainterPath, QPen
from PyQt5.QtWidgets import QLabel, QApplication
from core.user_input import UserInputHandler
from core.annotation_manager import AnnotationType
import fitz
import math
import time

class ClickablePageLabel(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.text_data = None
        self.word_data = None
        self.char_data = []  # Store character-level data
        self.zoom_level = 1.0
        self.start_pos = None
        self.end_pos = None
        self.selection_rects = []
        self.dark_mode = False
        self.setMouseTracking(True)
        
        # Enhanced selection state
        self.selection_start_index = None
        self.selection_end_index = None
        self.selected_chars = []
        self.is_selecting = False
        self._all_chars = []  # Augmented character data with line/word info
        
        # Click handling for double/triple click
        self.last_press_time = 0
        self.last_double_click_time = 0
        
        # Link handling
        self.links = []
        self.hovered_link = None
        self.page_index = -1
        
        self.search_highlights = []
        self.current_search_highlight_index = -1
        
        # Annotations
        self.annotations = []

        self.input_handler = UserInputHandler(parent)
        
        # Drawing state
        self.is_drawing_mode = False
        self.current_drawing_tool = AnnotationType.FREEHAND
        self.current_drawing_color = (255, 0, 0)
        self.current_drawing_stroke_width = 2.0
        self.current_drawing_filled = False
        self.current_drawing_points = []
        self.is_currently_drawing = False

    def set_page_data(self, pixmap, text_data, word_data, zoom_level, dark_mode, 
                      search_highlights=None, current_highlight_index=-1, annotations=None,
                      page_index=-1, pdf_page=None):
        """Enhanced set_page_data with character-level data and links."""
        self.setPixmap(pixmap)
        self.text_data = text_data
        self.word_data = word_data
        self.zoom_level = zoom_level
        self.dark_mode = dark_mode
        self.selection_rects = []
        self.page_index = page_index
        
        self.search_highlights = search_highlights if search_highlights else []
        self.current_search_highlight_index = current_highlight_index
        self.annotations = annotations if annotations else []
        
        # Extract character-level data and links
        self._extract_char_data()
        if pdf_page:
            self._extract_links(pdf_page)
        
        self._build_augmented_char_list()
        self.clear_selection()
        self.update()

    def _extract_char_data(self):
        """Extract character-level position data from text_data."""
        self.char_data = []
        
        if not self.text_data or 'blocks' not in self.text_data:
            return
        
        char_index = 0
        for block in self.text_data['blocks']:
            if block.get('type') != 0:  # Only text blocks
                continue
                
            for line in block.get('lines', []):
                for span in line.get('spans', []):
                    text = span.get('text', '')
                    bbox = span.get('bbox', [0, 0, 0, 0])
                    
                    if not text:
                        continue
                    
                    # Calculate character positions within the span
                    span_width = bbox[2] - bbox[0]
                    if len(text) > 0 and span_width > 0:
                        char_width = span_width / len(text)
                        
                        for i, char in enumerate(text):
                            char_x0 = bbox[0] + (i * char_width)
                            char_x1 = bbox[0] + ((i + 1) * char_width)
                            
                            self.char_data.append({
                                'char': char,
                                'bbox': [char_x0, bbox[1], char_x1, bbox[3]],
                                'span_idx': len(self.char_data),
                                'line_bbox': line.get('bbox', [0, 0, 0, 0]),
                                'block_no': block.get('number', 0),
                                'line_no': line.get('number', 0),
                                'char_index': char_index
                            })
                            char_index += 1

    def _extract_links(self, pdf_page):
        """Extract clickable links from the PDF page."""
        self.links = []
        
        try:
            for link in pdf_page.get_links():
                link_rect = link.get('from', fitz.Rect())
                link_data = {
                    'rect': [link_rect.x0, link_rect.y0, link_rect.x1, link_rect.y1],
                    'uri': link.get('uri', ''),
                    'page': link.get('page', -1),
                    'kind': link.get('kind', 0)  # 1=goto, 2=uri, 3=launch, etc.
                }
                self.links.append(link_data)
        except Exception as e:
            print(f"Error extracting links: {e}")

    def _build_augmented_char_list(self):
        """Build character list with line and word indices for smart selection."""
        if not self.char_data:
            self._all_chars = []
            return
        
        # Sort by reading order
        temp_chars = sorted(self.char_data, key=lambda c: (c['bbox'][1], c['bbox'][0]))
        
        # Augment with line and word info
        self._all_chars = []
        current_line_index = 0
        current_word_index = 0
        last_y = -1
        last_x_end = -1
        
        for i, char_data in enumerate(temp_chars):
            bbox = char_data['bbox']
            char = char_data['char']
            
            # Check for new line (significant y-position change)
            if last_y != -1 and abs(bbox[1] - last_y) > 3:
                current_line_index += 1
                current_word_index += 1  # New line always means new word
            # Check for new word (space between characters)
            elif last_x_end != -1 and (bbox[0] - last_x_end) > (bbox[2] - bbox[0]) * 0.3:
                current_word_index += 1
            
            # Add augmented data
            char_data['line_index'] = current_line_index
            char_data['word_index'] = current_word_index
            self._all_chars.append(char_data)
            
            # Update state
            last_y = bbox[1]
            last_x_end = bbox[2]
            
            # Whitespace always ends a word
            if char.isspace():
                current_word_index += 1

    def _get_link_at_pos(self, pos):
        """Check if there's a link at the given position."""
        if not self.links:
            return None
        
        for link in self.links:
            rect = QRectF(
                link['rect'][0] * self.zoom_level,
                link['rect'][1] * self.zoom_level,
                (link['rect'][2] - link['rect'][0]) * self.zoom_level,
                (link['rect'][3] - link['rect'][1]) * self.zoom_level
            )
            
            if rect.contains(pos):
                return link
        return None

    def _get_char_index_at_pos(self, pos_in_page):
        """Find the index of the character closest to the given page coordinates."""
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
        
        # Check if click is on blank space (too far from any character)
        closest_bbox = self._all_chars[closest_index]['bbox']
        char_width = closest_bbox[2] - closest_bbox[0]
        char_height = closest_bbox[3] - closest_bbox[1]
        max_allowed_dist = max(char_width, char_height) * 1.5
        
        if min_dist_sq > max_allowed_dist**2:
            return None  # Click is on blank space
            
        return closest_index

    def _screen_to_page_coords(self, screen_pos):
        """Convert screen coordinates to page coordinates."""
        return (
            screen_pos.x() / self.zoom_level,
            screen_pos.y() / self.zoom_level
        )

    def mouseDoubleClickEvent(self, event):
        """Handle double-clicks to select a word."""
        self.last_double_click_time = time.time()
        
        if self.is_drawing_mode or event.button() != Qt.LeftButton:
            return
            
        pos_in_page = self._screen_to_page_coords(event.pos())
        char_index = self._get_char_index_at_pos(pos_in_page)
        
        if char_index is not None:
            self._select_word_at_index(char_index)
            self.is_selecting = False  # Don't start a drag
            self._emit_selection_changed()

    def mousePressEvent(self, event):
        """Handle single-clicks (drag selection) and triple-clicks (line selection)."""
        if event.button() == Qt.LeftButton:
            
            # Handle Drawing
            if self.is_drawing_mode:
                self.is_currently_drawing = True
                self.current_drawing_points = [self._screen_to_page_coords(event.pos())]
                self.update()
                return
            
            # Handle Link Clicking
            link = self._get_link_at_pos(event.pos())
            if link and not (event.modifiers() & Qt.ControlModifier):
                self._handle_link_click(link)
                return
            
            # Handle Triple-Click (line selection)
            current_time = time.time()
            double_click_interval = QApplication.instance().doubleClickInterval() / 1000.0
            
            if (current_time - self.last_double_click_time) < double_click_interval:
                # Triple click detected!
                self.last_double_click_time = 0
                
                pos_in_page = self._screen_to_page_coords(event.pos())
                char_index = self._get_char_index_at_pos(pos_in_page)
                
                if char_index is not None:
                    self._select_line_at_index(char_index)
                    self.is_selecting = False
                    self._emit_selection_changed()
                return
            
            # Handle Single-Click (start drag selection)
            self.last_press_time = time.time()
            
            pos_in_page = self._screen_to_page_coords(event.pos())
            char_index = self._get_char_index_at_pos(pos_in_page)
            
            # Click on blank space: deselect
            if char_index is None:
                self.clear_selection()
                self._emit_selection_changed()
                self.is_selecting = False
                return
            
            # Start new selection
            self.is_selecting = True
            self.selection_start_index = char_index
            self.selection_end_index = None

    def mouseMoveEvent(self, event):
        """Handle mouse move for selection drag, link hovering, or drawing."""
        pos_in_page = self._screen_to_page_coords(event.pos())
        
        # Handle Drawing
        if self.is_drawing_mode and self.is_currently_drawing:
            self.current_drawing_points.append(pos_in_page)
            self.update()
            return
        
        # Handle Text Selection Drag
        if self.is_selecting and event.buttons() & Qt.LeftButton:
            char_index = self._get_char_index_at_pos(pos_in_page)
            if char_index is not None:
                if self.selection_end_index != char_index:
                    self.selection_end_index = char_index
                    self._update_selection()
                    self.update()
        
        # Handle Link Hovering
        elif not self.is_selecting:
            self._update_hover_state(event.pos())
            
    def mouseReleaseEvent(self, event):        
        """Handle mouse release for selection or drawing."""
        if event.button() == Qt.LeftButton:
            
            # Handle Drawing
            if self.is_drawing_mode and self.is_currently_drawing:
                self.is_currently_drawing = False
                pos_in_page = self._screen_to_page_coords(event.pos())
                self.current_drawing_points.append(pos_in_page)
                self._finalize_drawing()
                self.current_drawing_points = []
                self.update()
                return
            
            # Handle Text Selection
            if self.is_selecting:
                self.is_selecting = False
                self._emit_selection_changed()

    def _handle_link_click(self, link):
        """Handle clicking on a link."""
        if link['kind'] == 2 and link['uri']:  # External URI
            QDesktopServices.openUrl(QUrl(link['uri']))
        elif link['kind'] == 1 and link['page'] >= 0:  # Internal page link
            # Navigate to the target page
            main_window = self.parent()
            while main_window and not hasattr(main_window, 'page_manager'):
                main_window = main_window.parent()
            
            if main_window and hasattr(main_window, 'page_manager'):
                main_window.page_manager.jump_to_page(link['page'] + 1)

    def _select_word_at_index(self, index):
        """Select all characters belonging to the same word, including surrounding spaces."""
        if index is None or not self._all_chars:
            return
            
        target_word_index = self._all_chars[index]['word_index']
        target_line_index = self._all_chars[index]['line_index']
        
        # Find start of the word
        start_idx = index
        while (start_idx > 0 and 
               self._all_chars[start_idx - 1]['word_index'] == target_word_index and
               self._all_chars[start_idx - 1]['line_index'] == target_line_index):
            start_idx -= 1
            
        # Find end of the word
        end_idx = index
        while (end_idx < len(self._all_chars) - 1 and 
               self._all_chars[end_idx + 1]['word_index'] == target_word_index and
               self._all_chars[end_idx + 1]['line_index'] == target_line_index):
            end_idx += 1
            
        # QOL: Include space before the word if it exists
        if (start_idx > 0 and 
            self._all_chars[start_idx - 1]['line_index'] == target_line_index and
            self._all_chars[start_idx - 1]['char'].isspace()):
            start_idx -= 1
            
        # QOL: Include space after the word if it exists
        if (end_idx < len(self._all_chars) - 1 and 
            self._all_chars[end_idx + 1]['line_index'] == target_line_index and
            self._all_chars[end_idx + 1]['char'].isspace()):
            end_idx += 1
            
        self.selection_start_index = start_idx
        self.selection_end_index = end_idx
        self._update_selection()
        self.update()

    def _select_line_at_index(self, index):
        """Select all characters belonging to the same line."""
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
        self.selection_rects = []
        
        if (self.selection_start_index is None or 
            self.selection_end_index is None or 
            not self._all_chars):
            return
        
        start_idx = min(self.selection_start_index, self.selection_end_index)
        end_idx = max(self.selection_start_index, self.selection_end_index)
        
        if start_idx == -1 or end_idx == -1:
            return
            
        # Build selected chars list
        for i in range(start_idx, end_idx + 1):
            char_data = self._all_chars[i]
            self.selected_chars.append((char_data['char'], char_data['bbox']))
        
        # Build selection rectangles (merged by line for efficiency)
        self.selection_rects = self._get_char_selection_rects()

    def _get_char_selection_rects(self):
        """Generate selection rectangles for selected characters."""
        if not self.selected_chars:
            return []
        
        selection_rects = []
        current_rect = None
        last_line = None
        
        for char, bbox in self.selected_chars:
            # Determine if this char is on the same line as the previous
            char_line = bbox[1]  # Use y-coordinate as line indicator
            
            if last_line is not None and abs(char_line - last_line) > 3:
                # New line - save current rect and start new one
                if current_rect:
                    selection_rects.append(current_rect)
                current_rect = QRect(
                    int(bbox[0] * self.zoom_level),
                    int(bbox[1] * self.zoom_level),
                    int((bbox[2] - bbox[0]) * self.zoom_level),
                    int((bbox[3] - bbox[1]) * self.zoom_level)
                )
            elif current_rect:
                # Same line - extend current rectangle
                char_rect = QRect(
                    int(bbox[0] * self.zoom_level),
                    int(bbox[1] * self.zoom_level),
                    int((bbox[2] - bbox[0]) * self.zoom_level),
                    int((bbox[3] - bbox[1]) * self.zoom_level)
                )
                current_rect = current_rect.united(char_rect)
            else:
                # First character
                current_rect = QRect(
                    int(bbox[0] * self.zoom_level),
                    int(bbox[1] * self.zoom_level),
                    int((bbox[2] - bbox[0]) * self.zoom_level),
                    int((bbox[3] - bbox[1]) * self.zoom_level)
                )
            
            last_line = char_line
        
        if current_rect:
            selection_rects.append(current_rect)
        
        return selection_rects

    def _update_hover_state(self, pos):
        """Update link hover state and cursor."""
        old_hovered_link = self.hovered_link
        self.hovered_link = self._get_link_at_pos(pos)
        
        # Update cursor
        if self.is_drawing_mode:
            cursor = Qt.CrossCursor
        elif self.hovered_link:
            cursor = Qt.PointingHandCursor
        else:
            cursor = Qt.IBeamCursor
        
        if self.cursor().shape() != cursor:
            self.setCursor(cursor)
        
        # Repaint if hover state changed
        if old_hovered_link != self.hovered_link:
            self.update()

    def _emit_selection_changed(self):
        """Emit selection changed signal if possible."""
        text = self.get_selected_text()
        # If the main window has a handler for selection changes, call it
        main_window = self.parent()
        while main_window and not hasattr(main_window, 'on_text_selection_changed'):
            main_window = main_window.parent()
        if main_window and hasattr(main_window, 'on_text_selection_changed'):
            main_window.on_text_selection_changed(text)

    def get_selected_text(self, strip_single_word_spaces=True):
        """
        Get text from selected characters with proper spacing.
        
        Args:
            strip_single_word_spaces: If True and only one word is selected,
                                    strip leading/trailing spaces for cleaner copying
        """
        if not self.selected_chars:
            return ""
        
        result = []
        last_y = None
        last_x = None
        last_bbox = None
        
        for char, bbox in self.selected_chars:
            if last_y is not None:
                y_diff = abs(bbox[1] - last_y)
                if y_diff > 3:  # New line
                    result.append('\n')
                    last_x = None
                elif last_x is not None and last_bbox is not None:
                    gap = bbox[0] - last_x
                    last_char_width = last_bbox[2] - last_bbox[0]
                    if gap > last_char_width * 0.3:  # Space between words
                        result.append(' ')
            
            result.append(char)
            last_y = bbox[1]
            last_x = bbox[2]
            last_bbox = bbox
        
        text = ''.join(result)
        
        # QOL: If we're getting text for copying (not display) and it's a single word selection,
        # strip the surrounding spaces we added for visual selection
        if strip_single_word_spaces and self._is_single_word_selection():
            text = text.strip()
        
        return text
    
    def _is_single_word_selection(self):
        """Check if the current selection is a single word (used for smart space stripping)."""
        if (self.selection_start_index is None or 
            self.selection_end_index is None or 
            not self._all_chars):
            return False
        
        start_idx = min(self.selection_start_index, self.selection_end_index)
        end_idx = max(self.selection_start_index, self.selection_end_index)
        
        # Check if all selected chars (excluding spaces) belong to the same word
        word_indices = set()
        for i in range(start_idx, end_idx + 1):
            if i < len(self._all_chars):
                char_data = self._all_chars[i]
                if not char_data['char'].isspace():
                    word_indices.add(char_data['word_index'])
        
        return len(word_indices) == 1
    
    def get_selected_quads(self):
        """Get quads for selected characters grouped by line for annotation."""
        if not self.selected_chars:
            return []
        
        quads = []
        lines = {}
        
        # Group selected characters by line
        for char, bbox in self.selected_chars:
            line_y = bbox[1]  # Use y-coordinate as line indicator
            
            # Find which line this belongs to
            line_key = None
            for existing_line_y in lines.keys():
                if abs(line_y - existing_line_y) < 3:
                    line_key = existing_line_y
                    break
            
            if line_key is None:
                line_key = line_y
                lines[line_key] = []
            
            lines[line_key].append(bbox)
        
        # Create quads for each line
        for line_y in sorted(lines.keys()):
            bboxes = lines[line_y]
            if not bboxes:
                continue
                
            # Get bounding box for the line
            min_x = min(bbox[0] for bbox in bboxes)
            max_x = max(bbox[2] for bbox in bboxes)
            min_y = min(bbox[1] for bbox in bboxes)
            max_y = max(bbox[3] for bbox in bboxes)
            
            # Create quad (8 values: 4 corners)
            quad = [min_x, min_y, max_x, min_y, min_x, max_y, max_x, max_y]
            quads.append(quad)
        
        return quads

    def clear_selection(self):
        """Clear the current text selection."""
        self.selected_chars = []
        self.selection_rects = []
        self.selection_start_index = None
        self.selection_end_index = None
        self.update()

    def set_search_highlights(self, highlights, current_index=-1):
        self.search_highlights = highlights
        self.current_search_highlight_index = current_index
        self.update()

    def _finalize_drawing(self):
        """Create an annotation from the current drawing."""
        if len(self.current_drawing_points) < 2:
            return
        
        from helpers.annotations import Annotation
        
        main_window = self.parent()
        while main_window and not hasattr(main_window, 'annotation_manager'):
            main_window = main_window.parent()

        if main_window:
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
                main_window._refresh_current_page()
                
    def paintEvent(self, event):
        super().paintEvent(event)
        
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        buffer = QImage(self.size(), QImage.Format_ARGB32_Premultiplied)
        buffer.fill(Qt.transparent)
        
        buf_painter = QPainter(buffer)
        buf_painter.setCompositionMode(QPainter.CompositionMode_Source)
        buf_painter.setRenderHint(QPainter.Antialiasing)
        buf_painter.setPen(Qt.NoPen)
        
        # Draw link highlights (subtle)
        if self.hovered_link and not self.is_drawing_mode:
            link_rect = self.hovered_link['rect']
            hover_rect = QRectF(
                link_rect[0] * self.zoom_level,
                link_rect[1] * self.zoom_level,
                (link_rect[2] - link_rect[0]) * self.zoom_level,
                (link_rect[3] - link_rect[1]) * self.zoom_level
            )
            hover_color = QColor(100, 149, 237, 30)  # Light blue, very transparent
            buf_painter.setBrush(QBrush(hover_color))
            buf_painter.drawRect(hover_rect)
            buf_painter.setBrush(Qt.NoBrush)
        
        # Draw Search Highlights
        if 0 <= self.current_search_highlight_index < len(self.search_highlights):
            current_rect = self.search_highlights[self.current_search_highlight_index]
            current_highlight_rect = QRectF(
                current_rect.x0 * self.zoom_level,
                current_rect.y0 * self.zoom_level,
                current_rect.width * self.zoom_level,
                current_rect.height * self.zoom_level
            )
            if self.dark_mode:
                current_highlight_color = QColor(255, 255, 0, 100)
            else:
                current_highlight_color = QColor(0, 89, 195, 100)
                
            buf_painter.setBrush(QBrush(current_highlight_color))
            buf_painter.drawRect(current_highlight_rect)
            buf_painter.setBrush(Qt.NoBrush)

        # Draw Annotations
        for annotation in self.annotations:
            color = QColor(annotation.color[0], annotation.color[1], annotation.color[2], 100)
            
            if annotation.annotation_type == AnnotationType.HIGHLIGHT:
                buf_painter.setBrush(QBrush(color))
                for quad in annotation.quads:
                    rect = QRectF(
                        quad[0] * self.zoom_level,
                        quad[1] * self.zoom_level,
                        (quad[2] - quad[0]) * self.zoom_level,
                        (quad[5] - quad[1]) * self.zoom_level
                    )
                    buf_painter.drawRect(rect)
                buf_painter.setBrush(Qt.NoBrush)
            
            elif annotation.annotation_type == AnnotationType.UNDERLINE:
                buf_painter.setPen(color)
                for quad in annotation.quads:
                    line_y = quad[5] * self.zoom_level
                    buf_painter.drawLine(
                        int(quad[0] * self.zoom_level),
                        int(line_y),
                        int(quad[2] * self.zoom_level),
                        int(line_y)
                    )
                buf_painter.setPen(Qt.NoPen)
            
            # Drawing annotations
            elif annotation.annotation_type in [AnnotationType.FREEHAND, AnnotationType.LINE, 
                                            AnnotationType.ARROW, AnnotationType.RECTANGLE, 
                                            AnnotationType.CIRCLE]:
                
                if not annotation.points or len(annotation.points) < 2:
                    continue
                
                solid_color = QColor(annotation.color[0], annotation.color[1], annotation.color[2], 255)
                pen = QPen(solid_color, annotation.stroke_width)
                buf_painter.setPen(pen)
                
                if annotation.annotation_type == AnnotationType.FREEHAND:
                    if annotation.filled:
                        buf_painter.setBrush(QBrush(solid_color))
                    
                    path = QPainterPath()
                    first_point = annotation.points[0]
                    path.moveTo(first_point[0] * self.zoom_level, first_point[1] * self.zoom_level)
                    for point in annotation.points[1:]:
                        path.lineTo(point[0] * self.zoom_level, point[1] * self.zoom_level)
                    buf_painter.drawPath(path)
                    
                    if annotation.filled:
                        buf_painter.setBrush(Qt.NoBrush)
                
                elif annotation.annotation_type == AnnotationType.LINE:
                    start = annotation.points[0]
                    end = annotation.points[-1]
                    buf_painter.drawLine(
                        int(start[0] * self.zoom_level), int(start[1] * self.zoom_level),
                        int(end[0] * self.zoom_level), int(end[1] * self.zoom_level)
                    )
                
                elif annotation.annotation_type == AnnotationType.ARROW:
                    start = annotation.points[0]
                    end = annotation.points[-1]
                    
                    buf_painter.drawLine(
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
                    
                    buf_painter.drawLine(QPointF(end[0] * self.zoom_level, end[1] * self.zoom_level), arrow_p1)
                    buf_painter.drawLine(QPointF(end[0] * self.zoom_level, end[1] * self.zoom_level), arrow_p2)
                
                elif annotation.annotation_type == AnnotationType.RECTANGLE:
                    start = annotation.points[0]
                    end = annotation.points[-1]
                    
                    x = min(start[0], end[0]) * self.zoom_level
                    y = min(start[1], end[1]) * self.zoom_level
                    width = abs(end[0] - start[0]) * self.zoom_level
                    height = abs(end[1] - start[1]) * self.zoom_level
                    
                    if annotation.filled:
                        buf_painter.setBrush(QBrush(solid_color))
                    buf_painter.drawRect(QRectF(x, y, width, height))
                    if annotation.filled:
                        buf_painter.setBrush(Qt.NoBrush)
                
                elif annotation.annotation_type == AnnotationType.CIRCLE:
                    start = annotation.points[0]
                    end = annotation.points[-1]
                    
                    x = min(start[0], end[0]) * self.zoom_level
                    y = min(start[1], end[1]) * self.zoom_level
                    width = abs(end[0] - start[0]) * self.zoom_level
                    height = abs(end[1] - start[1]) * self.zoom_level
                    
                    if annotation.filled:
                        buf_painter.setBrush(QBrush(solid_color))
                    buf_painter.drawEllipse(QRectF(x, y, width, height))
                    if annotation.filled:
                        buf_painter.setBrush(Qt.NoBrush)
                
                buf_painter.setPen(Qt.NoPen)

        # Draw current drawing in progress
        if self.is_currently_drawing and len(self.current_drawing_points) >= 2:
            preview_color = QColor(self.current_drawing_color[0], 
                                self.current_drawing_color[1], 
                                self.current_drawing_color[2], 150)
            
            pen = QPen(preview_color, self.current_drawing_stroke_width)
            buf_painter.setPen(pen)
            
            if self.current_drawing_tool == AnnotationType.FREEHAND:
                if self.current_drawing_filled:
                    buf_painter.setBrush(QBrush(preview_color))
                path = QPainterPath()
                first_point = self.current_drawing_points[0]
                path.moveTo(first_point[0] * self.zoom_level, first_point[1] * self.zoom_level)
                for point in self.current_drawing_points[1:]:
                    path.lineTo(point[0] * self.zoom_level, point[1] * self.zoom_level)
                buf_painter.drawPath(path)
                if self.current_drawing_filled:
                    buf_painter.setBrush(Qt.NoBrush)
            
            elif self.current_drawing_tool == AnnotationType.LINE:
                start = self.current_drawing_points[0]
                end = self.current_drawing_points[-1]
                buf_painter.drawLine(
                    int(start[0] * self.zoom_level), int(start[1] * self.zoom_level),
                    int(end[0] * self.zoom_level), int(end[1] * self.zoom_level)
                )
            
            elif self.current_drawing_tool == AnnotationType.ARROW:
                start = self.current_drawing_points[0]
                end = self.current_drawing_points[-1]
                
                buf_painter.drawLine(
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
                
                buf_painter.drawLine(QPointF(end[0] * self.zoom_level, end[1] * self.zoom_level), arrow_p1)
                buf_painter.drawLine(QPointF(end[0] * self.zoom_level, end[1] * self.zoom_level), arrow_p2)
            
            elif self.current_drawing_tool == AnnotationType.RECTANGLE:
                start = self.current_drawing_points[0]
                end = self.current_drawing_points[-1]
                
                x = min(start[0], end[0]) * self.zoom_level
                y = min(start[1], end[1]) * self.zoom_level
                width = abs(end[0] - start[0]) * self.zoom_level
                height = abs(end[1] - start[1]) * self.zoom_level
                
                if self.current_drawing_filled:
                    buf_painter.setBrush(QBrush(preview_color))
                buf_painter.drawRect(QRectF(x, y, width, height))
                if self.current_drawing_filled:
                    buf_painter.setBrush(Qt.NoBrush)
            
            elif self.current_drawing_tool == AnnotationType.CIRCLE:
                start = self.current_drawing_points[0]
                end = self.current_drawing_points[-1]
                
                x = min(start[0], end[0]) * self.zoom_level
                y = min(start[1], end[1]) * self.zoom_level
                width = abs(end[0] - start[0]) * self.zoom_level
                height = abs(end[1] - start[1]) * self.zoom_level
                
                if self.current_drawing_filled:
                    buf_painter.setBrush(QBrush(preview_color))
                buf_painter.drawEllipse(QRectF(x, y, width, height))
                if self.current_drawing_filled:
                    buf_painter.setBrush(Qt.NoBrush)
            
            buf_painter.setPen(Qt.NoPen)

        # Draw Text Selection Highlights
        if self.selection_rects:
            if self.dark_mode:
                selection_color = QColor(255, 255, 0, 100)
            else:
                selection_color = QColor(0, 89, 195, 100)
                
            buf_painter.setBrush(QBrush(selection_color))
            
            for rect in self.selection_rects:
                buf_painter.drawRect(rect)
            
            buf_painter.setBrush(Qt.NoBrush)
        
        buf_painter.end()
        painter.setCompositionMode(QPainter.CompositionMode_SourceOver)
        painter.drawImage(0, 0, buffer)
        painter.end()
    
    def get_selection_rects(self):
        return self.selection_rects
    
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
        
        if self.is_drawing_mode:
            self.setCursor(Qt.CrossCursor)
        else:
            self.setCursor(Qt.IBeamCursor)
from PyQt5.QtCore import Qt, QRect, QRectF, pyqtSignal
from PyQt5.QtGui import QPainter, QColor, QBrush, QImage, QCursor
from PyQt5.QtWidgets import QLabel, QMenu, QMessageBox
from core.user_input import UserInputHandler
from core.annotation_manager import AnnotationType

# Custom widget to display a page image and handle text selection
class ClickablePageLabel(QLabel):
    # Signals for annotation operations
    annotation_selected = pyqtSignal(object)  # Emits selected annotation
    annotation_delete_requested = pyqtSignal(object)  # Emits annotation to delete
    
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
        self.selected_annotation = None
        self.hovered_annotation = None

        self.input_handler = UserInputHandler(parent)
        
        # NEW: Drawing state
        self.is_drawing_mode = False
        self.current_drawing_tool = AnnotationType.FREEHAND
        self.current_drawing_color = (255, 0, 0)
        self.current_drawing_stroke_width = 2.0
        self.current_drawing_filled = False
        self.current_drawing_points = []  # Points for current shape being drawn
        self.is_currently_drawing = False  # Whether user is actively drawing right now
        
        # Context menu for annotations
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)
        
        # Enable keyboard focus
        self.setFocusPolicy(Qt.StrongFocus)

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
        self.selected_annotation = None
        self.hovered_annotation = None

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

    def show_context_menu(self, position):
        """Show context menu for annotation operations."""
        # Check if there's an annotation at this position
        main_window = self.get_main_window()
        if not main_window:
            return
            
        # Find which page this label represents
        page_index = self.get_page_index()
        if page_index is None:
            return
        
        # Check for annotation at click position
        annotation = main_window.annotation_manager.get_annotation_at_point(
            page_index, position.x(), position.y(), self.zoom_level
        )
        
        if annotation:
            menu = QMenu(self)
            
            # Add delete action
            delete_action = menu.addAction("Delete Annotation")
            delete_action.triggered.connect(lambda: self.delete_annotation(annotation))
            
            # Add edit color action for highlights
            if annotation.annotation_type == AnnotationType.HIGHLIGHT:
                edit_color_action = menu.addAction("Change Color")
                edit_color_action.triggered.connect(lambda: self.edit_annotation_color(annotation))
            
            menu.exec_(self.mapToGlobal(position))

    def mousePressEvent(self, event):
        # Ensure this widget has focus for keyboard shortcuts
        self.setFocus()
        
        if self.is_drawing_mode and event.button() == Qt.LeftButton:
            # Start drawing
            self.is_currently_drawing = True
            self.current_drawing_points = [(event.pos().x() / self.zoom_level, 
                                            event.pos().y() / self.zoom_level)]
            self.update()
        elif event.button() == Qt.LeftButton:
            # Check for annotation selection first
            main_window = self.get_main_window()
            if main_window:
                page_index = self.get_page_index()
                if page_index is not None:
                    annotation = main_window.annotation_manager.get_annotation_at_point(
                        page_index, event.pos().x(), event.pos().y(), self.zoom_level
                    )
                    
                    if annotation and event.modifiers() & Qt.ControlModifier:
                        # Ctrl+Click on annotation to select it
                        self.selected_annotation = annotation
                        main_window.annotation_manager.selected_annotation = annotation
                        self.annotation_selected.emit(annotation)
                        self.update()
                        return
                    elif not annotation:
                        # Click on empty space - deselect annotation
                        if self.selected_annotation:
                            self.selected_annotation = None
                            if main_window:
                                main_window.annotation_manager.selected_annotation = None
                            self.update()
            
            # Normal text selection
            self.input_handler.handle_page_label_mouse_press(self, event)

    def mouseMoveEvent(self, event):
        # Check for annotation hover
        if not self.is_drawing_mode and not self.is_currently_drawing:
            main_window = self.get_main_window()
            if main_window:
                page_index = self.get_page_index()
                if page_index is not None:
                    annotation = main_window.annotation_manager.get_annotation_at_point(
                        page_index, event.pos().x(), event.pos().y(), self.zoom_level
                    )
                    
                    if annotation != self.hovered_annotation:
                        self.hovered_annotation = annotation
                        if annotation:
                            self.setCursor(Qt.PointingHandCursor)
                        else:
                            self.setCursor(Qt.ArrowCursor if not self.is_drawing_mode else Qt.CrossCursor)
                        self.update()
        
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

    def keyPressEvent(self, event):
        """Handle keyboard shortcuts for annotations."""
        if event.key() == Qt.Key_Delete or event.key() == Qt.Key_Backspace:
            if self.selected_annotation:
                self.delete_annotation(self.selected_annotation)
                event.accept()
                return
        
        super().keyPressEvent(event)

    def delete_annotation(self, annotation):
        """Delete the specified annotation."""
        main_window = self.get_main_window()
        if main_window:
            reply = QMessageBox.question(
                self,
                "Delete Annotation",
                "Are you sure you want to delete this annotation?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                if main_window.annotation_manager.remove_annotation(annotation):
                    self.selected_annotation = None
                    main_window._refresh_current_page()

    def edit_annotation_color(self, annotation):
        """Edit the color of an annotation."""
        from PyQt5.QtWidgets import QColorDialog
        
        initial_color = QColor(annotation.color[0], annotation.color[1], annotation.color[2])
        color = QColorDialog.getColor(initial_color, self, "Choose New Color")
        
        if color.isValid():
            main_window = self.get_main_window()
            if main_window:
                # Create a new annotation with updated color
                from helpers.annotations import Annotation
                new_annotation = Annotation(
                    page_index=annotation.page_index,
                    annotation_type=annotation.annotation_type,
                    color=(color.red(), color.green(), color.blue()),
                    quads=annotation.quads,
                    points=annotation.points,
                    stroke_width=annotation.stroke_width,
                    filled=annotation.filled
                )
                
                # Update the annotation
                if main_window.annotation_manager.update_annotation(annotation, new_annotation):
                    main_window._refresh_current_page()

    def get_main_window(self):
        """Get the main window through parent chain."""
        main_window = self.parent()
        while main_window and not hasattr(main_window, 'annotation_manager'):
            main_window = main_window.parent()
        return main_window

    def get_page_index(self):
        """Find which page this label represents."""
        main_window = self.get_main_window()
        if main_window:
            for idx, label in main_window.loaded_pages.items():
                if label == self:
                    return idx
        return None

    def _finalize_drawing(self):
        """Create an annotation from the current drawing."""
        
        if len(self.current_drawing_points) < 2:
            return  # Need at least 2 points
        
        # Emit signal to parent to create annotation
        # We'll handle this through the main window
        from helpers.annotations import Annotation
        
        main_window = self.get_main_window()
        page_index = self.get_page_index()
        
        if main_window and page_index is not None:
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
            if self.dark_mode:
                current_highlight_color = QColor(255, 255, 0, 100)
            else:
                current_highlight_color = QColor(0, 89, 195, 100)
                
            buf_painter.setBrush(QBrush(current_highlight_color))
            buf_painter.drawRect(current_highlight_rect)
            buf_painter.setBrush(Qt.NoBrush)

        # --- Draw Annotations onto the buffer ---
        
        for annotation in self.annotations:
            # Check if this annotation is selected or hovered
            is_selected = (annotation == self.selected_annotation or 
                          annotation == (self.get_main_window().annotation_manager.selected_annotation 
                                       if self.get_main_window() else None))
            is_hovered = annotation == self.hovered_annotation
            
            # Adjust opacity and add selection outline
            if is_selected:
                opacity = 150
            elif is_hovered:
                opacity = 120
            else:
                opacity = 100
                
            color = QColor(annotation.color[0], annotation.color[1], annotation.color[2], opacity)
            
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
                    
                    # Draw selection outline
                    if is_selected:
                        from PyQt5.QtGui import QPen
                        outline_pen = QPen(QColor(0, 120, 255), 2)
                        buf_painter.setPen(outline_pen)
                        buf_painter.setBrush(Qt.NoBrush)
                        buf_painter.drawRect(rect)
                        buf_painter.setPen(Qt.NoPen)
                        buf_painter.setBrush(QBrush(color))
                        
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
                
                from PyQt5.QtGui import QPen, QPainterPath
                from PyQt5.QtCore import QPointF
                import math
                
                solid_color = QColor(annotation.color[0], annotation.color[1], annotation.color[2], 255)
                
                # Add selection glow for freehand
                if is_selected and annotation.annotation_type == AnnotationType.FREEHAND:
                    glow_pen = QPen(QColor(0, 120, 255, 100), annotation.stroke_width + 4)
                    buf_painter.setPen(glow_pen)
                    
                    path = QPainterPath()
                    first_point = annotation.points[0]
                    path.moveTo(first_point[0] * self.zoom_level, first_point[1] * self.zoom_level)
                    for point in annotation.points[1:]:
                        path.lineTo(point[0] * self.zoom_level, point[1] * self.zoom_level)
                    buf_painter.drawPath(path)
                
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
                
                buf_painter.setPen(Qt.NoPen)

        # --- Draw current drawing in progress (real-time preview) ---
        
        if self.is_currently_drawing and len(self.current_drawing_points) >= 2:
            preview_color = QColor(self.current_drawing_color[0], 
                                self.current_drawing_color[1], 
                                self.current_drawing_color[2], 150)
            
            from PyQt5.QtGui import QPen, QPainterPath
            from PyQt5.QtCore import QPointF
            import math
            
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
            
            buf_painter.setPen(Qt.NoPen)

        # --- Draw Text Selection Highlights onto the buffer ---

        if self.selection_rects:
            if self.dark_mode:
                selection_color = QColor(255, 255, 0, 100)
            else:
                selection_color = QColor(0, 89, 195, 100)
                
            buf_painter.setBrush(QBrush(selection_color))
            
            for rect in self.selection_rects:
                buf_painter.drawRect(rect)
            
            buf_painter.setBrush(Qt.NoBrush)
        
        # IMPORTANT: End the buffer painter BEFORE using it elsewhere
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
"""
Interactive page label with character-level selection and link support.
"""

from typing import TYPE_CHECKING, List, Optional, Tuple

from PyQt5.QtCore import QPointF, QRectF, Qt, QTimer, pyqtSignal
from PyQt5.QtGui import (
    QBrush,
    QColor,
    QCursor,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPen,
)
from PyQt5.QtWidgets import QApplication, QLabel, QToolTip

from core.annotations import AnnotationType
from core.page.link_layer import LinkInfo, LinkType
from core.page.page_model import InteractionType, PageModel
from core.page.text_layer import CharacterInfo
from core.selection.selection_manager import SelectionManager

if TYPE_CHECKING:
    from controllers.link_handler import LinkNavigationHandler


class InteractivePageLabel(QLabel):
    """
    Page widget with character-level selection and clickable links.

    Features:
    - Character-level text selection
    - Double-click to select word
    - Triple-click to select line
    - Clickable links with hover effects
    - Link tooltips
    - Drawing mode support
    - Annotation display
    """

    # Signals
    link_clicked = pyqtSignal(object)  # LinkInfo
    link_hovered = pyqtSignal(object)  # LinkInfo or None
    selection_changed = pyqtSignal()
    character_clicked = pyqtSignal(int, object)  # page_index, CharacterInfo

    def __init__(
        self,
        page_model: PageModel,
        zoom: float,
        selection_manager: SelectionManager,
        parent=None,
    ):
        super().__init__(parent)

        self.page_model = page_model
        self.zoom = zoom
        self.selection_manager = selection_manager
        self.dark_mode = False

        # Interaction state
        self._is_selecting = False
        self._hovered_link: Optional[LinkInfo] = None
        self._click_count = 0
        self._click_timer = QTimer()
        self._click_timer.setSingleShot(True)
        self._click_timer.timeout.connect(self._reset_click_count)
        self._last_click_pos: Optional[QPointF] = None

        # Drawing mode state
        self._is_drawing_mode = False
        self._is_drawing = False
        self._drawing_points: List[Tuple[float, float]] = []
        self._drawing_tool = AnnotationType.FREEHAND
        self._drawing_color = (255, 0, 0)
        self._drawing_stroke_width = 2.0
        self._drawing_filled = False

        # Annotations for this page
        self.annotations = []

        # Search highlights
        self.search_highlights = []
        self.current_search_highlight_index = -1

        # Link handler reference
        self.link_handler: Optional["LinkNavigationHandler"] = None

        # Setup
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self._render()

    def _render(self):
        """Render the page pixmap."""
        pixmap = self.page_model.render_pixmap(self.zoom, self.dark_mode)
        self.setPixmap(pixmap)
        self.setFixedSize(pixmap.size())

    def set_zoom(self, zoom: float):
        """Update zoom level and re-render."""
        if self.zoom != zoom:
            self.zoom = zoom
            self._render()
            self.update()

    def set_dark_mode(self, dark_mode: bool):
        """Update dark mode and re-render."""
        if self.dark_mode != dark_mode:
            self.dark_mode = dark_mode
            self._render()
            self.update()

    def set_annotations(self, annotations: list):
        """Set annotations to display on this page."""
        self.annotations = annotations
        self.update()

    def set_drawing_mode(
        self, enabled: bool, tool=None, color=None, stroke_width=None, filled=None
    ):
        """Enable or disable drawing mode."""
        self._is_drawing_mode = enabled
        if tool is not None:
            self._drawing_tool = tool
        if color is not None:
            self._drawing_color = color
        if stroke_width is not None:
            self._drawing_stroke_width = stroke_width
        if filled is not None:
            self._drawing_filled = filled

        self.setCursor(Qt.CrossCursor if enabled else Qt.ArrowCursor)

    def _to_pdf_coords(self, pos) -> Tuple[float, float]:
        """Convert widget coordinates to PDF coordinates."""
        return pos.x() / self.zoom, pos.y() / self.zoom

    def _to_screen_coords(self, pdf_x: float, pdf_y: float) -> Tuple[float, float]:
        """Convert PDF coordinates to screen coordinates."""
        return pdf_x * self.zoom, pdf_y * self.zoom

    # Mouse event handlers

    def mousePressEvent(self, event: QMouseEvent):
        self.setFocus()

        if event.button() != Qt.LeftButton:
            return super().mousePressEvent(event)

        # Handle drawing mode
        if self._is_drawing_mode:
            self._start_drawing(event.pos())
            return

        pos = event.pos()
        pdf_x, pdf_y = self._to_pdf_coords(pos)

        # Check what's at this position
        element = self.page_model.get_element_at_point(pos.x(), pos.y(), self.zoom)

        # Handle click counting for double/triple click
        if self._last_click_pos and (pos - self._last_click_pos).manhattanLength() < 5:
            self._click_count += 1
        else:
            self._click_count = 1

        self._last_click_pos = QPointF(pos)
        self._click_timer.start(400)  # Reset after 400ms

        # Handle based on element type
        if element.type == InteractionType.LINK:
            # Don't start selection on links
            return

        elif element.type == InteractionType.TEXT:
            char: CharacterInfo = element.element

            if self._click_count == 3:
                # Triple click: select line
                self.selection_manager.select_line_at(self.page_model.page_index, char)
            elif self._click_count == 2:
                # Double click: select word
                self.selection_manager.select_word_at(self.page_model.page_index, char)
            else:
                # Single click: start selection
                self._is_selecting = True

                if event.modifiers() & Qt.ShiftModifier:
                    # Shift+click: extend selection
                    self.selection_manager.extend_selection(
                        self.page_model.page_index, char
                    )
                else:
                    # Normal click: start new selection
                    self.selection_manager.start_selection(
                        self.page_model.page_index, char
                    )

            self.selection_changed.emit()
            self.update()

        else:
            # Clicked on empty area
            if not (event.modifiers() & Qt.ShiftModifier):
                self.selection_manager.clear()
                self.update()

    def mouseMoveEvent(self, event: QMouseEvent):
        pos = event.pos()

        # Handle drawing
        if self._is_drawing_mode and self._is_drawing:
            self._continue_drawing(pos)
            return

        # Handle selection dragging
        if self._is_selecting and (event.buttons() & Qt.LeftButton):
            element = self.page_model.get_element_at_point(pos.x(), pos.y(), self.zoom)

            if element.type == InteractionType.TEXT:
                self.selection_manager.extend_selection(
                    self.page_model.page_index, element.element
                )
                self.selection_changed.emit()
                self.update()
            return

        # Handle hover effects
        element = self.page_model.get_element_at_point(pos.x(), pos.y(), self.zoom)

        if element.type == InteractionType.LINK:
            link: LinkInfo = element.element

            if link != self._hovered_link:
                self._hovered_link = link
                self.link_hovered.emit(link)
                self.setCursor(Qt.PointingHandCursor)

                # Show tooltip
                if self.link_handler:
                    tooltip = self.link_handler.get_link_tooltip(link)
                    QToolTip.showText(event.globalPos(), tooltip, self)

                self.update()

        elif element.type == InteractionType.TEXT:
            if self._hovered_link:
                self._hovered_link = None
                self.link_hovered.emit(None)
                self.update()
            self.setCursor(Qt.IBeamCursor)

        else:
            if self._hovered_link:
                self._hovered_link = None
                self.link_hovered.emit(None)
                self.update()
            self.setCursor(Qt.ArrowCursor)

    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() != Qt.LeftButton:
            return super().mouseReleaseEvent(event)

        # Handle drawing
        if self._is_drawing_mode and self._is_drawing:
            self._finish_drawing(event.pos())
            return

        # Handle link click
        if self._hovered_link and not self._is_selecting:
            self.link_clicked.emit(self._hovered_link)

            if self.link_handler:
                self.link_handler.handle_link_click(self._hovered_link)

        # Finish selection
        if self._is_selecting:
            self._is_selecting = False
            self.selection_manager.finish_selection()

    def _reset_click_count(self):
        """Reset click count after timeout."""
        self._click_count = 0

    # Drawing methods

    def _start_drawing(self, pos):
        """Start a drawing operation."""
        self._is_drawing = True
        pdf_x, pdf_y = self._to_pdf_coords(pos)
        self._drawing_points = [(pdf_x, pdf_y)]
        self.update()

    def _continue_drawing(self, pos):
        """Continue drawing operation."""
        pdf_x, pdf_y = self._to_pdf_coords(pos)
        self._drawing_points.append((pdf_x, pdf_y))
        self.update()

    def _finish_drawing(self, pos):
        """Finish drawing and create annotation."""
        pdf_x, pdf_y = self._to_pdf_coords(pos)
        self._drawing_points.append((pdf_x, pdf_y))
        self._is_drawing = False

        if len(self._drawing_points) >= 2:
            # Create annotation (emit signal for parent to handle)
            self._create_drawing_annotation()

        self._drawing_points = []
        self.update()

    def _create_drawing_annotation(self):
        """Create annotation from current drawing."""
        from core.annotations import Annotation

        # Get main window through parent chain
        main_window = self.parent()
        while main_window and not hasattr(main_window, "annotation_manager"):
            main_window = main_window.parent()

        if main_window and self._drawing_points:
            annotation = Annotation(
                page_index=self.page_model.page_index,
                annotation_type=self._drawing_tool,
                color=self._drawing_color,
                points=self._drawing_points.copy(),
                stroke_width=self._drawing_stroke_width,
                filled=self._drawing_filled,
            )
            main_window.annotation_manager.add_annotation(annotation)
            main_window._refresh_current_page()

    # Paint methods

    def paintEvent(self, event):
        try:
            super().paintEvent(event)

            painter = QPainter(self)
            painter.setRenderHint(QPainter.Antialiasing)

            self._paint_selection(painter)
            self._paint_search_highlights(painter)
            self._paint_link_hover(painter)
            self._paint_annotations(painter)

            if self._is_drawing and self._drawing_points:
                self._paint_drawing_preview(painter)

            painter.end()
        except Exception as e:
            print(f"PAINT ERROR: {e}")
            import traceback

            traceback.print_exc()

    def _paint_selection(self, painter: QPainter):
        """Paint text selection highlights."""
        selection = self.selection_manager.get_selection_for_page(
            self.page_model.page_index
        )

        if not selection or not selection.rects:
            return

        # Selection color
        if self.dark_mode:
            color = QColor(255, 255, 0, 100)
        else:
            color = QColor(0, 89, 195, 100)

        painter.setBrush(QBrush(color))
        painter.setPen(Qt.NoPen)

        for rect in selection.rects:
            screen_rect = QRectF(
                rect[0] * self.zoom,
                rect[1] * self.zoom,
                (rect[2] - rect[0]) * self.zoom,
                (rect[3] - rect[1]) * self.zoom,
            )
            painter.drawRect(screen_rect)

    def _paint_search_highlights(self, painter: QPainter):
        """Paint search result highlights."""
        if not self.search_highlights:
            return

        for i, rect in enumerate(self.search_highlights):
            try:
                # Handle fitz.Rect objects (legacy)
                if hasattr(rect, "x0"):
                    x0, y0 = rect.x0, rect.y0
                    w, h = rect.width, rect.height
                # Handle tuple formats
                elif isinstance(rect, (tuple, list)):
                    if len(rect) == 6:
                        # Format: (x0, y0, x1, y1, width, height)
                        x0, y0, x1, y1, w, h = rect
                    elif len(rect) == 4:
                        # Format: (x0, y0, x1, y1)
                        x0, y0, x1, y1 = rect
                        w, h = x1 - x0, y1 - y0
                    else:
                        continue  # Skip invalid format
                else:
                    continue  # Skip unknown type

                screen_rect = QRectF(
                    x0 * self.zoom, y0 * self.zoom, w * self.zoom, h * self.zoom
                )

                # Current result gets different color
                if i == self.current_search_highlight_index:
                    color = (
                        QColor(255, 165, 0, 150)
                        if self.dark_mode
                        else QColor(255, 140, 0, 150)
                    )
                else:
                    color = (
                        QColor(255, 255, 0, 80)
                        if self.dark_mode
                        else QColor(255, 255, 0, 100)
                    )

                painter.setBrush(QBrush(color))
                painter.setPen(Qt.NoPen)
                painter.drawRect(screen_rect)
            except Exception as e:
                print(f"Error painting search highlight: {e}")
                continue

    def _paint_link_hover(self, painter: QPainter):
        """Paint link hover indication."""
        if not self._hovered_link:
            return

        bbox = self._hovered_link.bbox
        screen_rect = QRectF(
            bbox[0] * self.zoom,
            bbox[1] * self.zoom,
            (bbox[2] - bbox[0]) * self.zoom,
            (bbox[3] - bbox[1]) * self.zoom,
        )

        # Draw subtle underline
        pen = QPen(QColor(0, 100, 200, 150), 2)
        painter.setPen(pen)
        painter.drawLine(screen_rect.bottomLeft(), screen_rect.bottomRight())

        # Optional: draw subtle highlight
        painter.setBrush(QBrush(QColor(0, 100, 200, 30)))
        painter.setPen(Qt.NoPen)
        painter.drawRect(screen_rect)

    def _paint_annotations(self, painter: QPainter):
        """Paint annotations on this page."""
        for ann in self.annotations:
            if ann.annotation_type == AnnotationType.HIGHLIGHT:
                self._paint_highlight(painter, ann)
            elif ann.annotation_type == AnnotationType.UNDERLINE:
                self._paint_underline(painter, ann)
            elif ann.annotation_type == AnnotationType.FREEHAND:
                self._paint_freehand(painter, ann)

    def _paint_highlight(self, painter: QPainter, ann):
        """Paint a highlight annotation."""
        color = QColor(ann.color[0], ann.color[1], ann.color[2], 100)
        painter.setBrush(QBrush(color))
        painter.setPen(Qt.NoPen)

        for quad in ann.quads:
            rect = QRectF(
                quad[0] * self.zoom,
                quad[1] * self.zoom,
                (quad[2] - quad[0]) * self.zoom,
                (quad[5] - quad[1]) * self.zoom,
            )
            painter.drawRect(rect)

    def _paint_underline(self, painter: QPainter, ann):
        """Paint an underline annotation."""
        color = QColor(ann.color[0], ann.color[1], ann.color[2])
        painter.setPen(QPen(color, 2))

        for quad in ann.quads:
            y = quad[5] * self.zoom
            painter.drawLine(
                int(quad[0] * self.zoom), int(y), int(quad[2] * self.zoom), int(y)
            )

    def _paint_freehand(self, painter: QPainter, ann):
        """Paint a freehand drawing annotation."""
        if not ann.points or len(ann.points) < 2:
            return

        color = QColor(ann.color[0], ann.color[1], ann.color[2])
        painter.setPen(QPen(color, ann.stroke_width))

        if ann.filled:
            painter.setBrush(QBrush(color))

        path = QPainterPath()
        first = ann.points[0]
        path.moveTo(first[0] * self.zoom, first[1] * self.zoom)

        for point in ann.points[1:]:
            path.lineTo(point[0] * self.zoom, point[1] * self.zoom)

        painter.drawPath(path)

    def _paint_drawing_preview(self, painter: QPainter):
        """Paint the current drawing in progress."""
        if len(self._drawing_points) < 2:
            return

        color = QColor(
            self._drawing_color[0], self._drawing_color[1], self._drawing_color[2], 150
        )
        painter.setPen(QPen(color, self._drawing_stroke_width))

        path = QPainterPath()
        first = self._drawing_points[0]
        path.moveTo(first[0] * self.zoom, first[1] * self.zoom)

        for point in self._drawing_points[1:]:
            path.lineTo(point[0] * self.zoom, point[1] * self.zoom)

        painter.drawPath(path)

    def get_selected_text(self) -> str:
        """Get selected text on this page."""
        return self.selection_manager.get_selected_text()

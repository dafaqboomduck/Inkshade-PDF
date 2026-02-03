"""
Main application window for Inkshade PDF Reader.
Fully refactored to use controllers and reduce complexity.
"""

import os
from pathlib import Path
from typing import Dict, List, Optional

from PyQt5.QtCore import QSize, Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QColor, QIcon, QIntValidator, QKeySequence, QPainter, QPixmap
from PyQt5.QtWidgets import (
    QApplication,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressDialog,
    QScrollArea,
    QSizePolicy,
    QSpacerItem,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

# Controller imports
from controllers import (
    AnnotationController,
    LinkNavigationHandler,
    UserInputHandler,
    ViewController,
)
from core.annotations import AnnotationManager, AnnotationType

# Core imports
from core.document import PDFDocumentReader, PDFExporter
from core.export import ExportWorker
from core.page import PageModel
from core.search import PDFSearchEngine, SearchHighlight
from core.selection import SelectionManager
from styles import ThemeManager
from ui.toolbars import AnnotationToolbar, DrawingToolbar, SearchBar

# UI imports
from ui.widgets import PDFViewer, TOCWidget

# Utils and styles
from utils import get_icon_path, get_resource_path
from utils.warning_manager import WarningType, warning_manager


class MainWindow(QMainWindow):
    """Main application window with refactored architecture."""

    # Signals
    document_loaded = pyqtSignal(str)
    document_closed = pyqtSignal()
    theme_changed = pyqtSignal(bool)

    def __init__(self, file_path: Optional[str] = None):
        super().__init__()

        # Initialize core components
        self._init_core_components()

        # Initialize controllers
        self._init_controllers()

        # Setup UI
        self._setup_window()
        self._setup_ui()
        self._setup_connections()

        # Apply initial theme
        self._apply_theme()

        # Load file if provided
        if file_path and os.path.exists(file_path):
            self.load_pdf(file_path)

    def _init_core_components(self):
        """Initialize core business logic components."""
        # Document handling
        self.pdf_reader = PDFDocumentReader()
        self.pdf_exporter = PDFExporter()

        # Annotation system
        self.annotation_manager = AnnotationManager()

        # Search engine
        self.search_engine = PDFSearchEngine()

        # View state
        self.dark_mode = True
        self.zoom = 2.2
        self.base_zoom = 2.2
        self.page_spacing = 30
        self.page_height = None
        self.loaded_pages = {}
        self.current_page_index = 0

        # File state
        self.current_file_path: Optional[str] = None

        # Export worker (created when needed)
        self.export_worker: Optional[ExportWorker] = None

    def _init_controllers(self):
        """Initialize application controllers."""
        # Create scroll area and page container first
        self.page_container = QWidget()
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setWidget(self.page_container)

        # Input handler
        self.input_handler = UserInputHandler(self)

        # View controller
        self.view_controller = ViewController(self.scroll_area, self.page_container)
        self.view_controller.zoom_level = self.zoom
        self.view_controller.base_zoom = self.base_zoom
        self.view_controller.page_spacing = self.page_spacing

        # Annotation controller
        self.annotation_controller = AnnotationController(self.annotation_manager, self)

        # PDF viewer (now uses new architecture internally)
        self.page_manager = PDFViewer(
            main_window=self,
            page_container_widget=self.page_container,
            scroll_area_widget=self.scroll_area,
            pdf_reader_core=self.pdf_reader,
            annotation_manager=self.annotation_manager,
        )

        # Link handler is now created inside page_manager
        # But we can also access it if needed:
        self.link_handler = self.page_manager.link_handler

    def _setup_window(self):
        """Setup main window properties."""
        self.setWindowTitle("Inkshade PDF")
        self.setWindowIcon(QIcon(get_icon_path("inkshade.ico")))

        # Set minimum size
        self.setMinimumSize(800, 600)

    def _setup_ui(self):
        """Setup the user interface."""
        # Create toolbar
        self._create_toolbar()

        # Create TOC widget
        self.toc_widget = TOCWidget()
        self.toc_widget.hide()

        # Create floating toolbars
        self._create_floating_toolbars()

        # Setup main layout
        self._setup_layout()

        # Position floating toolbars
        QTimer.singleShot(0, self._update_toolbar_positions)

    def _create_toolbar(self):
        """Create the top toolbar."""
        self.top_frame = QFrame()
        self.top_frame.setObjectName("TopFrame")
        self.top_layout = QHBoxLayout(self.top_frame)
        self.top_layout.setContentsMargins(10, 8, 10, 8)
        self.top_layout.setSpacing(8)

        # Store button references for theme updates
        self.icon_buttons = []

        # File operations
        self._add_toolbar_button("open-icon.png", "Open PDF (Ctrl+O)", self.open_pdf)
        self._add_toolbar_button("close-icon.png", "Close PDF (Ctrl+W)", self.close_pdf)

        self._add_toolbar_separator()

        # Navigation
        self.toc_button = self._add_toolbar_button(
            "toc-icon.png", "Table of Contents", self.toggle_toc_view
        )
        self.toc_button.setVisible(False)  # Hidden until PDF with TOC is loaded

        self._add_toolbar_button(
            "search-icon.png", "Search (Ctrl+F)", self.show_search_bar
        )

        self._add_toolbar_spacer(15)

        # File info
        self.file_name_label = QLabel("No PDF Loaded", self.top_frame)
        self.file_name_label.setStyleSheet("font-weight: bold; color: #8899AA;")
        self.top_layout.addWidget(self.file_name_label)

        self._add_toolbar_spacer(40, expanding=True)

        # Page navigation
        self._create_page_navigation()

        self._add_toolbar_separator()
        self._add_toolbar_spacer(15)

        # Zoom controls
        self._create_zoom_controls()

        self._add_toolbar_spacer(40, expanding=True)
        self._add_toolbar_separator()
        self._add_toolbar_spacer(15)

        # Tools
        self._add_toolbar_button(
            "annotate-icon.png", "Annotate Selection", self.show_annotation_toolbar
        )
        self._add_toolbar_button("draw-icon.png", "Draw", self.show_drawing_toolbar)
        self._add_toolbar_button(
            "save-icon.png", "Save PDF (Ctrl+S)", self.save_annotations_to_pdf
        )

        # Theme toggle
        self.toggle_button = self._add_toolbar_button(
            "dark-mode-icon.png", "Toggle Dark Mode", self.toggle_theme
        )

    def _add_toolbar_button(
        self, icon_name: str, tooltip: str, callback
    ) -> QToolButton:
        """Add a button to the toolbar."""
        btn = self.create_icon_button(
            f"resources/icons/{icon_name}", tooltip, self.top_frame
        )
        btn.clicked.connect(callback)
        self.top_layout.addWidget(btn)
        self.icon_buttons.append((btn, f"resources/icons/{icon_name}"))
        return btn

    def _add_toolbar_separator(self):
        """Add a separator to the toolbar."""
        separator = QFrame()
        separator.setFrameShape(QFrame.VLine)
        separator.setFrameShadow(QFrame.Sunken)
        separator.setStyleSheet("background-color: #555555; max-width: 1px;")
        self.top_layout.addWidget(separator)

    def _add_toolbar_spacer(self, width: int, expanding: bool = False):
        """Add a spacer to the toolbar."""
        policy = QSizePolicy.Expanding if expanding else QSizePolicy.Fixed
        spacer = QSpacerItem(width, 20, policy, QSizePolicy.Minimum)
        self.top_layout.addSpacerItem(spacer)

    def _create_page_navigation(self):
        """Create page navigation controls."""
        self.page_edit = QLineEdit("1", self.top_frame)
        self.page_edit.setObjectName("page_input")
        self.page_edit.setFixedWidth(50)
        self.page_edit.setAlignment(Qt.AlignCenter)
        self.page_edit.setValidator(QIntValidator(1, 1, self))
        self.page_edit.returnPressed.connect(self.page_number_changed)
        self.top_layout.addWidget(self.page_edit)

        self.total_page_label = QLabel("/ 0", self.top_frame)
        self.top_layout.addWidget(self.total_page_label)

    def _create_zoom_controls(self):
        """Create zoom controls."""
        self._add_toolbar_button(
            "zoom-out-icon.png", "Zoom Out", lambda: self.adjust_zoom(-20)
        )

        self.zoom_lineedit = QLineEdit("100", self.top_frame)
        self.zoom_lineedit.setObjectName("zoom_input")
        self.zoom_lineedit.setFixedWidth(50)
        self.zoom_lineedit.setAlignment(Qt.AlignCenter)
        self.zoom_lineedit.setValidator(QIntValidator(20, 300, self))
        self.zoom_lineedit.returnPressed.connect(self.manual_zoom_changed)
        self.top_layout.addWidget(self.zoom_lineedit)

        self._add_toolbar_button(
            "zoom-in-icon.png", "Zoom In", lambda: self.adjust_zoom(20)
        )

    def _create_floating_toolbars(self):
        """Create floating toolbars."""
        # Search bar
        self.search_bar = SearchBar(self)
        self.search_bar.search_requested.connect(self._execute_search)
        self.search_bar.next_result_requested.connect(self._find_next)
        self.search_bar.prev_result_requested.connect(self._find_prev)
        self.search_bar.close_requested.connect(self._clear_search)
        self.search_bar.raise_()

        # Annotation toolbar
        self.annotation_toolbar = AnnotationToolbar(self)
        self.annotation_toolbar.annotation_requested.connect(
            self._create_annotation_from_selection
        )
        self.annotation_toolbar.raise_()

        # Drawing toolbar
        self.drawing_toolbar = DrawingToolbar(self)
        self.drawing_toolbar.drawing_mode_changed.connect(self._on_drawing_mode_changed)
        self.drawing_toolbar.tool_changed.connect(self._on_drawing_tool_changed)
        self.drawing_toolbar.raise_()

    def _setup_layout(self):
        """Setup the main window layout."""
        # Horizontal layout for TOC and content
        content_layout = QHBoxLayout()
        content_layout.setSpacing(0)
        content_layout.setContentsMargins(0, 0, 0, 0)

        content_layout.addWidget(self.toc_widget)
        content_layout.addWidget(self.scroll_area)

        content_widget = QWidget()
        content_widget.setLayout(content_layout)

        # Main vertical layout
        main_layout = QVBoxLayout()
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(self.top_frame)
        main_layout.addWidget(content_widget)

        container = QWidget()
        container.setLayout(main_layout)
        self.setCentralWidget(container)

    def _setup_connections(self):
        """Setup signal/slot connections."""
        # View controller connections
        self.view_controller.page_changed.connect(self._on_page_changed)
        self.view_controller.zoom_changed.connect(self._on_zoom_changed)

        # Annotation controller connections
        self.annotation_controller.annotations_changed.connect(
            self._on_annotations_changed
        )

        # TOC connections
        self.toc_widget.toc_link_clicked.connect(self._handle_toc_click)

        # Scroll area connections
        self.scroll_area.verticalScrollBar().valueChanged.connect(self.on_scroll)

    def _apply_theme(self):
        """Apply the current theme."""
        ThemeManager.apply_theme(self, self.dark_mode)

        # Update icon colors
        self.update_icon_colors()

        # Apply theme to floating toolbars
        for toolbar in [self.search_bar, self.annotation_toolbar, self.drawing_toolbar]:
            ThemeManager.apply_theme(toolbar, self.dark_mode)

        self.theme_changed.emit(self.dark_mode)

    def _update_toolbar_positions(self):
        """Update positions of floating toolbars."""
        window_width = self.width()
        x = window_width - 18 - 300  # 18px margin, 300px toolbar width
        y = self.top_frame.height() + 20  # Below top frame

        for toolbar in [self.search_bar, self.annotation_toolbar, self.drawing_toolbar]:
            toolbar.move(x, y)

    def create_icon_button(
        self, icon_path: str, tooltip: str, parent: QWidget = None
    ) -> QToolButton:
        """Create an icon button with proper theming."""
        btn = QToolButton(parent)

        if os.path.exists(get_resource_path(icon_path)):
            pixmap = QPixmap(get_resource_path(icon_path))
            colored_pixmap = self._color_icon(pixmap)
            btn.setIcon(QIcon(colored_pixmap))
            btn.setIconSize(QSize(20, 20))

        btn.setToolTip(tooltip)
        btn.setFixedSize(36, 36)
        return btn

    def _color_icon(self, pixmap: QPixmap) -> QPixmap:
        """Color an icon based on theme."""
        colored = QPixmap(pixmap.size())
        colored.fill(Qt.transparent)

        painter = QPainter(colored)
        painter.setCompositionMode(QPainter.CompositionMode_Source)
        painter.drawPixmap(0, 0, pixmap)
        painter.setCompositionMode(QPainter.CompositionMode_SourceIn)

        color = QColor(181, 181, 197) if self.dark_mode else QColor(122, 137, 156)
        painter.fillRect(colored.rect(), color)
        painter.end()

        return colored

    def update_icon_colors(self):
        """Update all icon colors based on theme."""
        for btn, icon_path in self.icon_buttons:
            if os.path.exists(get_resource_path(icon_path)):
                pixmap = QPixmap(get_resource_path(icon_path))
                colored_pixmap = self._color_icon(pixmap)
                btn.setIcon(QIcon(colored_pixmap))

    # Document Management Methods

    def load_pdf(self, file_path: str):
        """Load a PDF file."""
        success, total_pages = self.pdf_reader.load_pdf(file_path)

        if not success:
            return

        # Update search engine
        self.search_engine.set_document(self.pdf_reader.doc)

        # Update view controller
        self.view_controller.set_document_info(total_pages)
        self.page_height = None  # Reset page height

        # Load annotations
        annotation_count = self.annotation_controller.load_annotations(file_path)
        if annotation_count > 0:
            QMessageBox.information(
                self,
                "Annotations Loaded",
                f"Loaded {annotation_count} existing annotation(s) from previous session.",
            )

        # Update UI
        self.current_file_path = file_path
        self.file_name_label.setText(os.path.basename(file_path))
        self.total_page_label.setText(f"/ {total_pages}")
        self.page_edit.setText("1")
        self.page_edit.setValidator(QIntValidator(1, total_pages, self))

        # Load TOC
        self.load_toc_data()

        # Clear and update pages
        self.page_manager.clear_all()
        self.scroll_area.verticalScrollBar().setValue(0)
        self.current_page_index = 0
        self.update_visible_pages()

        # Emit signal
        self.document_loaded.emit(file_path)

    def open_pdf(self):
        """Open a PDF file dialog."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Open PDF", "", "PDF Files (*.pdf)"
        )
        if file_path:
            self.load_pdf(file_path)
            self._update_undo_redo_buttons()

    def close_pdf(self):
        """Close the current PDF with one-time warning per session."""
        if not self.pdf_reader.is_loaded():
            return

        # Check for unsaved changes
        if self.annotation_manager.has_unsaved_changes:
            result = warning_manager.show_save_discard_cancel(
                self,
                WarningType.CLOSE_PDF_UNSAVED,
                "Unsaved Changes",
                "You have unsaved annotations. Do you want to save them before closing?",
                show_dont_ask=True,
            )

            if result == QMessageBox.Save:
                if not self.save_annotations_to_pdf():
                    return
            elif result == QMessageBox.Cancel:
                return
            elif result == QMessageBox.Discard:
                self.annotation_manager.delete_json_file()

        # Clear selection before closing
        self.page_manager.clear_selection()

        # Close document
        self.pdf_reader.close_document()
        self.search_engine.clear_search()
        self.annotation_manager.clear_all()
        self.view_controller.clear_all_pages()
        self.page_manager.clear_all()

        # Clear UI
        self.file_name_label.setText("No PDF Loaded")
        self.total_page_label.setText("/ 0")
        self.page_edit.setText("1")
        self.page_edit.setValidator(QIntValidator(1, 1, self))
        self.toc_widget.clear_toc()
        self.toc_widget.hide()
        self.toc_button.setVisible(False)

        # Hide toolbars
        self._hide_search_bar()
        self._hide_annotation_toolbar()
        self._hide_drawing_toolbar()

        # Reset state
        self.current_page_index = 0
        self.page_height = None
        self.loaded_pages.clear()
        self.scroll_area.verticalScrollBar().setValue(0)

        self.document_closed.emit()
        self._update_undo_redo_buttons()

    # TOC Methods

    def toggle_toc_view(self):
        """Toggle the Table of Contents view."""
        if self.toc_widget.isVisible():
            self.toc_widget.hide()
        else:
            self.toc_widget.show()
            self.load_toc_data()

    def load_toc_data(self):
        """Load TOC data into the widget."""
        toc_data = self.pdf_reader.get_toc()
        self.toc_widget.load_toc(toc_data)
        has_toc = bool(toc_data)
        self.toc_button.setVisible(has_toc)
        if not has_toc:
            self.toc_widget.hide()

    def _handle_toc_click(self, page_num: int, y_pos: float):
        """Handle TOC item clicks."""
        self.page_manager.jump_to_page(page_num, y_pos)

    # Page Navigation Methods

    def navigate_to_page(self, page_num: int, y_offset: float = 0.0):
        """
        Navigate to a specific page and position.

        Args:
            page_num: 1-based page number
            y_offset: Y-coordinate in PDF points (optional)
        """
        self.page_manager.jump_to_page(page_num, y_offset)

    def update_visible_pages(self, desired_page: Optional[int] = None):
        """Update visible pages."""
        if desired_page is not None:
            current_page = int(desired_page)
        elif self.page_height is None:
            current_page = self.current_page_index
        else:
            current_page = self.page_manager.get_current_page_index()

        self.current_page_index = current_page
        self.page_manager.update_visible_pages(current_page)

    def update_current_page_display(self):
        """Update the current page display in the toolbar."""
        if self.page_height is None:
            return

        self.current_page_index = self.page_manager.get_current_page_index()
        if not self.page_edit.hasFocus():
            self.page_edit.setText(str(self.current_page_index + 1))

    def on_scroll(self):
        """Handle scroll events."""
        self.update_visible_pages()
        self.update_current_page_display()

    def page_number_changed(self):
        """Handle page number input change."""
        if self.page_height is None:
            return

        try:
            page_num = int(self.page_edit.text())
            if 1 <= page_num <= self.pdf_reader.total_pages:
                self.page_manager.jump_to_page(page_num)
            else:
                self.page_edit.setText(str(self.current_page_index + 1))
        except (ValueError, IndexError):
            self.page_edit.setText(str(self.current_page_index + 1))

    def get_current_page_info(self):
        """Get current page scroll information."""
        return self.page_manager.get_scroll_info()

    # Zoom Methods

    def adjust_zoom(self, delta: int):
        """Adjust zoom level."""
        current_zoom_percent = int((self.zoom / self.base_zoom) * 100)
        new_zoom_percent = max(20, min(300, current_zoom_percent + delta))
        self.zoom_lineedit.setText(str(new_zoom_percent))
        self._handle_zoom_change(new_zoom_percent)

    def manual_zoom_changed(self):
        """Handle manual zoom input."""
        try:
            zoom_percent = int(self.zoom_lineedit.text())
            self._handle_zoom_change(zoom_percent)
        except ValueError:
            # Reset to current zoom
            current_zoom_percent = int((self.zoom / self.base_zoom) * 100)
            self.zoom_lineedit.setText(str(current_zoom_percent))

    def _handle_zoom_change(self, new_zoom_percent: int):
        """Handle zoom level change."""
        try:
            # Save current position
            current_page_index, offset_in_page = self.get_current_page_info()

            # Update zoom
            self.zoom = (new_zoom_percent / 100.0) * self.base_zoom
            self.page_manager.set_zoom(self.zoom)
            self.view_controller.set_zoom(new_zoom_percent)

            if self.pdf_reader.doc:
                # Clear and reload pages
                self.page_manager.clear_all()
                self.update_visible_pages()

                # Process events to update layout
                QApplication.processEvents()
                self.page_container.updateGeometry()
                self.scroll_area.updateGeometry()
                QApplication.processEvents()

                # Restore position
                QTimer.singleShot(
                    10,
                    lambda: self._restore_scroll_position(
                        current_page_index, offset_in_page
                    ),
                )

        except (ValueError, IndexError):
            current_zoom_percent = int((self.zoom / self.base_zoom) * 100)
            self.zoom_lineedit.setText(str(current_zoom_percent))

    def _restore_scroll_position(self, current_page_index: int, offset_in_page: int):
        """Restore scroll position after zoom change."""
        if self.page_height:
            target_y = (
                current_page_index * (self.page_height + self.page_spacing)
            ) + offset_in_page
            self.scroll_area.verticalScrollBar().setValue(int(target_y))

            # Restore search highlight if active
            if self.search_engine.search_results:
                self._jump_to_current_search_result()

    # Theme Methods

    def toggle_theme(self):
        """Toggle between dark and light themes."""
        self.dark_mode = not self.dark_mode

        # Update toggle button icon
        if self.dark_mode:
            icon_path = "resources/icons/dark-mode-icon.png"
            self.toggle_button.setToolTip("Switch to Light Mode")
        else:
            icon_path = "resources/icons/light-mode-icon.png"
            self.toggle_button.setToolTip("Switch to Dark Mode")

        # Update button icon with proper coloring
        if os.path.exists(get_resource_path(icon_path)):
            pixmap = QPixmap(get_resource_path(icon_path))
            colored_pixmap = self._color_icon(pixmap)
            self.toggle_button.setIcon(QIcon(colored_pixmap))

        # Apply theme
        self._apply_theme()
        self.page_manager.set_dark_mode(self.dark_mode)

        # Refresh pages if document is loaded
        if self.pdf_reader.doc:
            current_page_index, offset_in_page = self.get_current_page_info()
            self.page_manager.clear_all()
            self.update_visible_pages(desired_page=current_page_index)

            # Restore position
            QTimer.singleShot(
                0, lambda: self._restore_and_repaint(current_page_index, offset_in_page)
            )

    def _restore_and_repaint(self, current_page_index: int, offset_in_page: int):
        """Restore scroll position and repaint after theme change."""
        self._restore_scroll_position(current_page_index, offset_in_page)

        # Force repaint
        if self.current_page_index in self.loaded_pages:
            self.loaded_pages[self.current_page_index].repaint()
        self.page_container.repaint()
        self.scroll_area.viewport().repaint()

    # Search Methods

    def show_search_bar(self):
        """Show or hide the search bar."""
        if self.search_bar.isVisible():
            self.search_bar.hide()
        else:
            self.annotation_toolbar.hide()
            self.drawing_toolbar.hide()
            self.search_bar.show_bar()
            self.search_bar.raise_()

    def _hide_search_bar(self):
        """Hide the search bar."""
        self.search_bar.hide()
        self._clear_search()

    def _execute_search(self, search_term: str):
        """Execute a search."""
        try:
            if not search_term:
                self.search_bar.set_status("0 results")
                self.page_manager.update_page_highlights()
                return

            num_results = self.search_engine.execute_search(search_term)

            if num_results > 0:
                self._find_next()
            else:
                self.search_bar.set_status("0 results")
                self.page_manager.update_page_highlights()
        except Exception as e:
            print(f"SEARCH ERROR: {e}")
            import traceback

            traceback.print_exc()

    def _find_next(self):
        """Find next search result."""
        page_idx, rect = self.search_engine.next_result()
        self._jump_to_current_search_result()

    def _find_prev(self):
        """Find previous search result."""
        page_idx, rect = self.search_engine.previous_result()
        self._jump_to_current_search_result()

    def _jump_to_current_search_result(self):
        """Jump to the current search result."""
        page_idx, rect = self.search_engine.get_current_result()

        if page_idx is not None and rect is not None:
            # Convert rect to tuple BEFORE passing
            rect_tuple = (rect.x0, rect.y0, rect.x1, rect.y1, rect.width, rect.height)
            self.page_manager.jump_to_search_result(page_idx, rect_tuple)

            current_idx = self.search_engine.get_current_index()
            total_results = self.search_engine.get_result_count()
            self.search_bar.set_status(f"{current_idx + 1} of {total_results}")

    def _clear_search(self):
        """Clear search results."""
        self.search_engine.clear_search()
        self.search_bar.clear_search()
        self.page_manager.update_page_highlights()

    # Annotation Methods

    def show_annotation_toolbar(self):
        """Show or hide the annotation toolbar."""
        if self.annotation_toolbar.isVisible():
            self.annotation_toolbar.hide()
        else:
            self.search_bar.hide()
            self.drawing_toolbar.hide()
            self.annotation_toolbar.show()
            self.annotation_toolbar.raise_()

    def _hide_annotation_toolbar(self):
        """Hide the annotation toolbar."""
        self.annotation_toolbar.hide()

    def _create_annotation_from_selection(
        self, annotation_type: AnnotationType, color: tuple
    ):
        """Create an annotation from selected text."""
        if (
            self.pdf_reader.doc is None
            or self.current_page_index not in self.loaded_pages
        ):
            return

        current_page_widget = self.loaded_pages[self.current_page_index]
        selected_words = current_page_widget.selected_words

        success = self.annotation_controller.create_text_annotation(
            self.current_page_index, selected_words, annotation_type, color
        )

        if success:
            # Clear selection
            current_page_widget.selected_words.clear()
            current_page_widget.selection_rects = []
            self._refresh_current_page()

    def show_drawing_toolbar(self):
        """Show or hide the drawing toolbar."""
        if self.drawing_toolbar.isVisible():
            self.drawing_toolbar.hide()
        else:
            self.search_bar.hide()
            self.annotation_toolbar.hide()
            self.drawing_toolbar.show()
            self.drawing_toolbar.raise_()

    def _hide_drawing_toolbar(self):
        """Hide the drawing toolbar."""
        self.drawing_toolbar.hide()
        self.drawing_toolbar._close_toolbar()

    def _on_drawing_mode_changed(self, enabled: bool):
        """Handle drawing mode change."""
        tool_settings = self.drawing_toolbar.get_current_settings()
        tool, color, stroke_width, filled = tool_settings

        for label in self.loaded_pages.values():
            label.set_drawing_mode(enabled, tool, color, stroke_width, filled)

    def _on_drawing_tool_changed(
        self, tool: AnnotationType, color: tuple, stroke_width: float, filled: bool
    ):
        """Handle drawing tool change."""
        for label in self.loaded_pages.values():
            label.set_drawing_mode(
                self.drawing_toolbar.is_in_drawing_mode(),
                tool,
                color,
                stroke_width,
                filled,
            )

    def undo_annotation(self):
        """Undo the last annotation."""
        if self.annotation_controller.undo():
            self._refresh_all_visible_pages()
            self._update_undo_redo_buttons()

    def redo_annotation(self):
        """Redo the last undone annotation."""
        if self.annotation_controller.redo():
            self._refresh_all_visible_pages()
            self._update_undo_redo_buttons()

    def _update_undo_redo_buttons(self):
        """Update undo/redo button states."""
        # If you have undo/redo buttons, update their enabled state here
        pass

    def save_annotations_to_pdf(self) -> bool:
        """Save annotations to PDF file."""
        if not self.pdf_reader.doc or not self.annotation_manager.pdf_path:
            QMessageBox.warning(self, "No PDF", "No PDF document is currently loaded.")
            return False

        if self.annotation_manager.get_annotation_count() == 0:
            QMessageBox.information(
                self, "No Annotations", "There are no annotations to save."
            )
            return False

        # Get save location
        default_name = os.path.basename(self.annotation_manager.pdf_path)
        default_dir = os.path.dirname(self.annotation_manager.pdf_path)
        default_path = os.path.join(default_dir, default_name)

        output_path, _ = QFileDialog.getSaveFileName(
            self, "Save Annotated PDF", default_path, "PDF Files (*.pdf)"
        )

        if not output_path:
            return False

        # Store info before closing
        temp_annotations = self.annotation_manager.annotations.copy()
        original_pdf_path = self.annotation_manager.pdf_path
        saving_to_same_file = os.path.abspath(output_path) == os.path.abspath(
            original_pdf_path
        )

        # Close document before saving
        self.pdf_reader.close_document()

        # Create progress dialog
        progress = QProgressDialog(
            "Preparing to export annotations...", None, 0, 100, self
        )
        progress.setWindowTitle("Saving PDF")
        progress.setWindowModality(Qt.WindowModal)
        progress.setMinimumDuration(0)
        progress.setCancelButton(None)
        progress.setAutoClose(False)
        progress.setAutoReset(False)
        progress.show()

        # Create and configure worker thread
        self.export_worker = ExportWorker(
            original_pdf_path,
            output_path,
            temp_annotations,
            use_temp_file=saving_to_same_file,
        )

        # Connect signals
        def on_progress(message):
            progress.setLabelText(message)

        def on_page_progress(current, total):
            if total > 0:
                percent = int((current / total) * 100)
                progress.setValue(percent)
                progress.setLabelText(
                    f"Processing annotations: {current}/{total} pages"
                )

        def on_finished(success, message):
            progress.close()

            if success:
                # Delete JSON file and mark as saved
                self.annotation_manager.delete_json_file()
                self.annotation_manager.mark_saved()

                QMessageBox.information(self, "Success", message)

                # Reload the PDF
                self.load_pdf(output_path)
            else:
                QMessageBox.critical(self, "Save Failed", message)

                # Reopen original file
                self.load_pdf(original_pdf_path)

            # Clean up worker
            self.export_worker.deleteLater()
            self.export_worker = None

        self.export_worker.progress.connect(on_progress)
        self.export_worker.page_progress.connect(on_page_progress)
        self.export_worker.finished.connect(on_finished)

        # Start export
        self.export_worker.start()

        return True

    # Helper Methods

    def _refresh_current_page(self):
        """Refresh the current page display."""
        if self.current_page_index in self.loaded_pages:
            self.loaded_pages[self.current_page_index].deleteLater()
            del self.loaded_pages[self.current_page_index]

            # Also clear the page model cache
            if hasattr(self.page_manager, "page_models"):
                if self.current_page_index in self.page_manager.page_models:
                    self.page_manager.page_models[self.current_page_index].clear_cache()

            self.page_manager.update_visible_pages(self.current_page_index)

    def _refresh_all_visible_pages(self):
        """Refresh all currently visible pages."""
        # Clear all loaded pages
        for idx in list(self.loaded_pages.keys()):
            if idx in self.loaded_pages:
                self.loaded_pages[idx].deleteLater()
                del self.loaded_pages[idx]

        # Clear page model caches
        if hasattr(self.page_manager, "page_models"):
            for model in self.page_manager.page_models.values():
                model.clear_cache()

        self.update_visible_pages()

    def _on_page_changed(self, page_index: int):
        """Handle page change from view controller."""
        self.current_page_index = page_index
        if not self.page_edit.hasFocus():
            self.page_edit.setText(str(page_index + 1))

    def _on_zoom_changed(self, zoom_level: float):
        """Handle zoom change from view controller."""
        self.zoom = zoom_level
        self.page_manager.set_zoom(zoom_level)

        # Update zoom display
        zoom_percent = int((zoom_level / self.base_zoom) * 100)
        self.zoom_lineedit.setText(str(zoom_percent))

    def _on_annotations_changed(self):
        """Handle annotation changes."""
        self._refresh_current_page()
        self._update_undo_redo_buttons()

    def copy_selected_text(self):
        """Copy selected text to clipboard."""
        # Use the selection manager from page_manager
        text = self.page_manager.copy_selected_text()

        if text:
            import pyperclip

            pyperclip.copy(text)
        else:
            QMessageBox.information(self, "No Selection", "No text has been selected.")

    # Event Handlers

    def keyPressEvent(self, event):
        """Handle keyboard shortcuts."""
        # Undo/Redo
        if event.modifiers() & Qt.ControlModifier:
            if event.key() == Qt.Key_Z:
                if event.modifiers() & Qt.ShiftModifier:
                    self.redo_annotation()
                else:
                    self.undo_annotation()
                event.accept()
                return
            elif event.key() == Qt.Key_Y:
                self.redo_annotation()
                event.accept()
                return
            elif event.key() == Qt.Key_A:
                # Select all on current page
                self.page_manager.select_all_on_page(self.current_page_index)
                event.accept()
                return

        # Escape to clear selection
        if event.key() == Qt.Key_Escape:
            if self.search_bar.isVisible():
                self._hide_search_bar()
            else:
                self.page_manager.clear_selection()
            event.accept()
            return

        # Delegate to input handler for other shortcuts
        self.input_handler.handle_key_press(event)

    def resizeEvent(self, event):
        """Handle window resize."""
        super().resizeEvent(event)
        self._update_toolbar_positions()

    def closeEvent(self, event):
        """Handle window close with one-time warning per session."""
        if self.annotation_manager.has_unsaved_changes:
            # Use warning manager for potentially one-time warning
            result = warning_manager.show_save_discard_cancel(
                self,
                WarningType.EXIT_UNSAVED,
                "Unsaved Changes",
                "You have unsaved annotations. Do you want to save them before exiting?",
                show_dont_ask=True,  # Allow suppressing exit warnings
            )

            if result == QMessageBox.Save:
                if self.save_annotations_to_pdf():
                    self.annotation_manager.delete_json_file()
                    event.accept()
                else:
                    event.ignore()
            elif result == QMessageBox.Discard:
                self.annotation_manager.delete_json_file()
                event.accept()
            else:  # Cancel
                event.ignore()
        else:
            event.accept()

"""
PDF viewer widget - Updated to use new page architecture.
"""

from typing import Dict, List, Optional

from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtWidgets import QApplication

from controllers.link_handler import LinkNavigationHandler
from core.page import PageModel
from core.search import SearchHighlight
from core.selection import SelectionManager
from ui.widgets.page_label import InteractivePageLabel


class PDFViewer:
    """
    Manages PDF page display with character-level selection and links.

    Features:
    - Lazy page loading with buffer
    - Character-level text selection
    - Clickable links
    - Search highlighting
    - Annotation display
    - Drawing mode support
    """

    def __init__(
        self,
        main_window,
        page_container_widget,
        scroll_area_widget,
        pdf_reader_core,
        annotation_manager,
    ):
        self.main_window = main_window
        self.page_container = page_container_widget
        self.scroll_area = scroll_area_widget
        self.pdf_reader_core = pdf_reader_core
        self.annotation_manager = annotation_manager

        # View state from main window
        self.zoom = main_window.zoom
        self.dark_mode = main_window.dark_mode
        self.page_spacing = main_window.page_spacing

        # Page management
        self.page_models: Dict[int, PageModel] = {}
        self.loaded_pages: Dict[int, InteractivePageLabel] = main_window.loaded_pages
        self.page_height: Optional[int] = None

        # Selection manager (shared across all pages)
        self.selection_manager = SelectionManager()

        # Link handler
        self.link_handler = LinkNavigationHandler(main_window)
        self.link_handler.navigation_requested.connect(self._on_navigation_requested)

        # Page loading buffer
        self.page_buffer = 7  # Load pages within this range of current

        # Setup container
        self.page_container.setMinimumHeight(0)
        self.page_container.resizeEvent = self.container_resize_event

    def clear_all(self):
        """Clears all loaded pages and resets state."""
        # Clear page labels
        for label in self.loaded_pages.values():
            label.deleteLater()
        self.loaded_pages.clear()

        # Clear page models
        for model in self.page_models.values():
            model.unload()
        self.page_models.clear()

        # Clear selection
        self.selection_manager.clear()

        # Reset state
        self.page_height = None
        self.page_container.setMinimumHeight(0)

    def set_zoom(self, new_zoom: float):
        """Updates the zoom factor."""
        self.zoom = new_zoom

        # Clear pixmap caches in page models
        for model in self.page_models.values():
            model.clear_cache()

    def set_dark_mode(self, dark_mode: bool):
        """Updates dark mode setting."""
        self.dark_mode = dark_mode

        # Clear pixmap caches
        for model in self.page_models.values():
            model.clear_cache()

    def container_resize_event(self, event):
        """Repositions page labels when container size changes."""
        container_width = self.page_container.width()

        for idx, label in self.loaded_pages.items():
            if label.pixmap():
                pix_width = label.pixmap().width()
                x = (container_width - pix_width) // 2
                y = idx * (self.page_height + self.page_spacing)
                label.move(x, y)

        event.accept()

    def update_visible_pages(self, current_page_index: int):
        """
        Load and display pages near the current page.

        Args:
            current_page_index: The currently focused page index
        """
        if self.pdf_reader_core.doc is None or self.pdf_reader_core.total_pages == 0:
            return

        # Ensure we have at least one page loaded to get dimensions
        if self.page_height is None:
            if current_page_index not in self.loaded_pages:
                self._load_and_display_page(current_page_index)
                if self.page_height is None:
                    return

        total_pages = self.pdf_reader_core.total_pages
        start_index = max(0, current_page_index - self.page_buffer)
        end_index = min(total_pages - 1, current_page_index + self.page_buffer)

        # Unload pages outside the buffer
        pages_to_unload = [
            idx
            for idx in list(self.loaded_pages.keys())
            if idx < start_index or idx > end_index
        ]

        for idx in pages_to_unload:
            self.loaded_pages[idx].deleteLater()
            del self.loaded_pages[idx]

            # Also unload page model to free memory
            if idx in self.page_models:
                self.page_models[idx].unload()
                del self.page_models[idx]

        # Load missing pages
        for idx in range(start_index, end_index + 1):
            if idx not in self.loaded_pages:
                self._load_and_display_page(idx)

        # Update selection manager with current page models
        self.selection_manager.set_page_models(self.page_models)

    def _load_and_display_page(self, idx: int):
        """Render and display a single page."""
        # Get or create PageModel
        if idx not in self.page_models:
            self.page_models[idx] = PageModel(self.pdf_reader_core.doc, idx)

        page_model = self.page_models[idx]

        # Let Qt process events to prevent UI freeze/crash
        QApplication.processEvents()

        # Get search highlights
        rects_on_page = []
        current_idx_on_page = -1

        if hasattr(self.main_window, "search_engine"):
            search_engine = self.main_window.search_engine
            raw_rects, current_idx_on_page = SearchHighlight.get_highlights_for_page(
                search_engine, idx
            )
            for r in raw_rects:
                if hasattr(r, "x0"):
                    rects_on_page.append((r.x0, r.y0, r.x1, r.y1))
                else:
                    rects_on_page.append(r)

        annotations_on_page = self.annotation_manager.get_annotations_for_page(idx)

        # Let Qt breathe again before creating widget
        QApplication.processEvents()

        label = InteractivePageLabel(
            page_model=page_model,
            zoom=self.zoom,
            selection_manager=self.selection_manager,
            parent=self.page_container,
        )

        # Configure label
        label.set_dark_mode(self.dark_mode)
        label.set_annotations(annotations_on_page)
        label.link_handler = self.link_handler

        # Set search highlights
        label.search_highlights = rects_on_page
        label.current_search_highlight_index = current_idx_on_page

        # Set drawing mode if active
        if (
            hasattr(self.main_window, "drawing_toolbar")
            and self.main_window.drawing_toolbar.is_in_drawing_mode()
        ):
            tool_settings = self.main_window.drawing_toolbar.get_current_settings()
            tool, color, stroke_width, filled = tool_settings
            label.set_drawing_mode(True, tool, color, stroke_width, filled)

        # Connect signals
        label.link_clicked.connect(self._on_link_clicked)
        label.selection_changed.connect(self._on_selection_changed)

        label.setAlignment(Qt.AlignCenter)

        # Set page height if first page
        if self.page_height is None:
            pixmap = label.pixmap()
            if pixmap:
                self.page_height = pixmap.height()
                total_height = (
                    self.pdf_reader_core.total_pages
                    * (self.page_height + self.page_spacing)
                    - self.page_spacing
                )
                self.page_container.setMinimumHeight(total_height)
                self.main_window.page_height = self.page_height

        # Position the label
        container_width = self.page_container.width()
        pixmap = label.pixmap()
        if pixmap:
            x = (container_width - pixmap.width()) // 2
            y = idx * (self.page_height + self.page_spacing)
            label.setGeometry(x, y, pixmap.width(), pixmap.height())

        label.show()
        self.loaded_pages[idx] = label

        # Force update
        label.update()
        self.page_container.update()
        self.scroll_area.viewport().update()

    def get_current_page_index(self) -> int:
        """Calculate the index of the page centered in viewport."""
        if self.page_height is None or self.page_height == 0:
            return 0

        vsb = self.scroll_area.verticalScrollBar()
        scroll_val = vsb.value()
        viewport_height = self.scroll_area.viewport().height()
        H = self.page_height + self.page_spacing

        current_page = round(
            (scroll_val + viewport_height / 2 - self.page_height / 2) / H
        )
        current_page = max(0, min(self.pdf_reader_core.total_pages - 1, current_page))
        return current_page

    def get_scroll_info(self):
        """Returns current page index and offset for zoom operations."""
        if self.page_height is None or self.page_height == 0:
            return 0, 0

        vsb = self.scroll_area.verticalScrollBar()
        scroll_val = vsb.value()
        H = self.page_height + self.page_spacing
        current_page_index = int(scroll_val / H)
        offset_in_page = scroll_val % H
        return current_page_index, offset_in_page

    def jump_to_page(self, page_num: int, y_offset: float = 0.0):
        """
        Scroll to a specific page position.

        Args:
            page_num: 1-based page number
            y_offset: Y-coordinate in PDF points
        """
        if self.page_height is None or self.page_height == 0:
            return

        if not (1 <= page_num <= self.pdf_reader_core.total_pages):
            return

        page_start_y = (page_num - 1) * (self.page_height + self.page_spacing)

        if y_offset > 0:
            try:
                page = self.pdf_reader_core.doc.load_page(page_num - 1)
                page_rect = page.rect
                pdf_page_height = page_rect.height

                if y_offset <= pdf_page_height:
                    normalized_offset = y_offset / pdf_page_height
                    pixel_offset = normalized_offset * self.page_height

                    viewport_height = self.scroll_area.viewport().height()
                    target_y = (
                        page_start_y + pixel_offset - min(50, viewport_height * 0.1)
                    )
                    target_y = max(0, target_y)
                else:
                    target_y = page_start_y
            except Exception as e:
                print(f"Jump calculation failed: {e}")
                target_y = page_start_y
        else:
            target_y = page_start_y

        self.scroll_area.verticalScrollBar().setValue(int(target_y))

        # Update visible pages after scrolling
        QTimer.singleShot(50, lambda: self.main_window.update_visible_pages())

    def jump_to_search_result(self, page_idx: int, rect_tuple):
        """Scroll to center on a search result."""
        if page_idx is None or rect_tuple is None:
            return

        # Ensure pages are loaded first - this sets page_height
        if self.page_height is None:
            self._load_and_display_page(page_idx)
            if self.page_height is None:
                return

        # Make sure the target page and surrounding pages are loaded
        self.update_visible_pages(page_idx)

        # Process events to ensure pages are rendered
        QApplication.processEvents()

        # rect_tuple = (x0, y0, x1, y1, width, height)
        y0 = rect_tuple[1]
        height = (
            rect_tuple[5] if len(rect_tuple) > 5 else (rect_tuple[3] - rect_tuple[1])
        )

        # Calculate target scroll position
        viewport_height = self.scroll_area.viewport().height()
        scroll_offset = viewport_height / 2 - (height * self.zoom) / 2

        target_y = (
            (page_idx * (self.page_height + self.page_spacing))
            + (y0 * self.zoom)
            - scroll_offset
        )

        # Clamp to valid range
        max_scroll = self.scroll_area.verticalScrollBar().maximum()
        target_y = max(0, min(int(target_y), max_scroll))

        # Set scroll position
        self.scroll_area.verticalScrollBar().setValue(int(target_y))

        # Update highlights after a short delay
        QTimer.singleShot(50, lambda: self._finish_search_jump(page_idx))

    def _finish_search_jump(self, page_idx: int):
        """Complete the search jump after scroll."""
        # Ensure pages around target are loaded
        self.update_visible_pages(page_idx)
        # Update highlights on all loaded pages
        self.update_page_highlights()

    def update_page_highlights(self):
        """Update search highlights on all loaded pages."""
        try:
            for idx, label in self.loaded_pages.items():
                rects_on_page = []
                current_idx_on_page = -1

                if hasattr(self.main_window, "search_engine"):
                    search_engine = self.main_window.search_engine
                    raw_rects, current_idx_on_page = (
                        SearchHighlight.get_highlights_for_page(search_engine, idx)
                    )

                    # Convert fitz.Rect to tuples to avoid C++ object issues
                    for r in raw_rects:
                        if hasattr(r, "x0"):
                            rects_on_page.append((r.x0, r.y0, r.x1, r.y1))
                        else:
                            rects_on_page.append(r)

                label.search_highlights = rects_on_page
                label.current_search_highlight_index = current_idx_on_page
                label.update()
        except Exception as e:
            print(f"HIGHLIGHT ERROR: {e}")
            import traceback

            traceback.print_exc()

    def copy_selected_text(self) -> str:
        """Get all selected text for copying."""
        return self.selection_manager.get_selected_text()

    def clear_selection(self):
        """Clear text selection."""
        self.selection_manager.clear()
        for label in self.loaded_pages.values():
            label.update()

    def select_all_on_page(self, page_index: int):
        """Select all text on a specific page."""
        self.selection_manager.select_all(page_index)
        if page_index in self.loaded_pages:
            self.loaded_pages[page_index].update()

    # Signal handlers

    def _on_link_clicked(self, link):
        """Handle link click from page label."""
        # Link handler processes navigation automatically
        pass

    def _on_navigation_requested(self, page_num: int, y_offset: float):
        """Handle navigation request from link handler."""
        self.jump_to_page(page_num, y_offset)

    def _on_selection_changed(self):
        """Handle selection change from page label."""
        # Update all visible pages to show selection
        for label in self.loaded_pages.values():
            label.update()

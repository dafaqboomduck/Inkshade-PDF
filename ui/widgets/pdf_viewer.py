"""
PDF viewer widget - Updated to use new page architecture.
"""

from typing import Dict, List, Optional

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import QApplication

# Import sip for checking deleted widgets
try:
    import sip
except ImportError:
    sip = None

from controllers.link_handler import LinkNavigationHandler
from core.page import PageModel
from core.search import SearchHighlight
from core.selection import SelectionManager
from ui.widgets.page_label import InteractivePageLabel


class PDFViewer:
    """
    Manages PDF page display with character-level selection and links.
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
        self.page_buffer = 7

        # Re-entrancy guard
        self._updating_pages = False

        # Setup container
        self.page_container.setMinimumHeight(0)
        self.page_container.resizeEvent = self.container_resize_event

    # ===== Widget Safety Methods =====

    def _is_widget_valid(self, widget) -> bool:
        """Check if a Qt widget is still valid (not deleted)."""
        if widget is None:
            return False
        if sip is not None:
            try:
                return not sip.isdeleted(widget)
            except Exception:
                return False
        try:
            _ = widget.isVisible()
            return True
        except RuntimeError:
            return False

    def _safely_delete_label(
        self, label: InteractivePageLabel, immediate: bool = False
    ):
        """
        Safely disconnect signals and delete a page label.

        Args:
            label: The label to delete
            immediate: If True, delete immediately instead of using deleteLater()
        """
        if not self._is_widget_valid(label):
            return

        try:
            label.link_clicked.disconnect()
        except (TypeError, RuntimeError):
            pass

        try:
            label.selection_changed.disconnect()
        except (TypeError, RuntimeError):
            pass

        try:
            # Clear the pixmap to prevent visual artifacts
            label.clear()
            label.hide()
            label.setParent(None)

            if immediate:
                # Force immediate deletion - useful during zoom operations
                if sip is not None:
                    sip.delete(label)
                else:
                    label.deleteLater()
            else:
                label.deleteLater()
        except RuntimeError:
            pass

    # ===== Page Management Methods =====

    def clear_all(self, keep_dimensions: bool = False, immediate_delete: bool = False):
        """
        Clears all loaded pages and resets state.

        Args:
            keep_dimensions: If True, don't reset page_height or container height.
            immediate_delete: If True, delete widgets immediately (for zoom operations).
        """
        # Pop all items to avoid modification during iteration
        while self.loaded_pages:
            idx, label = self.loaded_pages.popitem()
            self._safely_delete_label(label, immediate=immediate_delete)

        # Clear page models
        model_keys = list(self.page_models.keys())
        for idx in model_keys:
            if idx in self.page_models:
                self.page_models[idx].unload()
        self.page_models.clear()

        # Clear selection
        self.selection_manager.clear()

        # Only reset dimensions if not keeping them
        if not keep_dimensions:
            self.page_height = None
            self.page_container.setMinimumHeight(0)

        # Force repaint of the container to clear any visual remnants
        self.page_container.update()
        self.page_container.repaint()

    def set_page_height(self, new_height: int):
        """Manually set page height (used during zoom to prevent flash)."""
        self.page_height = new_height
        if self.pdf_reader_core.total_pages > 0:
            total_height = (
                self.pdf_reader_core.total_pages
                * (self.page_height + self.page_spacing)
                - self.page_spacing
            )
            self.page_container.setMinimumHeight(total_height)
            self.main_window.page_height = self.page_height

    def set_zoom(self, new_zoom: float):
        """Updates the zoom factor."""
        self.zoom = new_zoom
        for model in list(self.page_models.values()):
            model.clear_cache()

    def set_dark_mode(self, dark_mode: bool):
        """Updates dark mode setting."""
        self.dark_mode = dark_mode
        for model in list(self.page_models.values()):
            model.clear_cache()

    def apply_zoom_to_pages(self, new_zoom: float):
        """
        Update zoom on all existing pages WITHOUT destroying them.
        """
        self.zoom = new_zoom

        if not self.loaded_pages or self.page_height is None:
            return False

        # Clear page model caches so they re-render at new zoom
        for model in self.page_models.values():
            model.clear_cache()

        # Re-render each label and get ACTUAL dimensions from pixmap
        actual_page_height = None
        container_width = self.page_container.width()

        for idx, label in list(self.loaded_pages.items()):
            if not self._is_widget_valid(label):
                continue

            # Re-render at new zoom
            label.set_zoom(new_zoom)

            pixmap = label.pixmap()
            if pixmap:
                # Get actual height from first rendered page
                if actual_page_height is None:
                    actual_page_height = pixmap.height()

                # Position using ACTUAL rendered height
                x = (container_width - pixmap.width()) // 2
                y = idx * (actual_page_height + self.page_spacing)
                label.setGeometry(x, y, pixmap.width(), pixmap.height())

        # Update page_height with actual rendered height
        if actual_page_height:
            self.page_height = actual_page_height
            self.main_window.page_height = actual_page_height

            # Update container height
            if self.pdf_reader_core.total_pages > 0:
                total_height = (
                    self.pdf_reader_core.total_pages
                    * (self.page_height + self.page_spacing)
                    - self.page_spacing
                )
                self.page_container.setMinimumHeight(total_height)

        return True

    def apply_dark_mode_to_pages(self, dark_mode: bool):
        """
        Update dark mode on all existing pages WITHOUT destroying them.
        """
        self.dark_mode = dark_mode

        if not self.loaded_pages:
            return False

        # Clear page model caches
        for model in self.page_models.values():
            model.clear_cache()

        # Update each existing label in place
        for label in list(self.loaded_pages.values()):
            if self._is_widget_valid(label):
                label.set_dark_mode(dark_mode)

        return True

    def refresh_page(self, page_index: int):
        """Refresh a single page (re-render with current settings)."""
        # Save scroll position to prevent jumping
        scroll_value = self.scroll_area.verticalScrollBar().value()

        if page_index in self.loaded_pages:
            label = self.loaded_pages.pop(page_index)
            self._safely_delete_label(label, immediate=True)

        if page_index in self.page_models:
            self.page_models[page_index].clear_cache()
            del self.page_models[page_index]

        QApplication.processEvents()
        self._load_and_display_page(page_index)

        # Restore scroll position
        self.scroll_area.verticalScrollBar().setValue(scroll_value)

    def refresh_all_pages(self):
        """Refresh all currently visible pages."""
        # Save scroll position to prevent jumping
        scroll_value = self.scroll_area.verticalScrollBar().value()
        current = self.get_current_page_index()

        self.clear_all(keep_dimensions=True, immediate_delete=True)
        QApplication.processEvents()
        self.update_visible_pages(current)

        # Restore scroll position
        self.scroll_area.verticalScrollBar().setValue(scroll_value)

    def container_resize_event(self, event):
        """Repositions page labels when container size changes."""
        container_width = self.page_container.width()

        for idx, label in list(self.loaded_pages.items()):
            if self._is_widget_valid(label) and label.pixmap():
                pix_width = label.pixmap().width()
                x = (container_width - pix_width) // 2
                y = idx * (self.page_height + self.page_spacing)
                label.move(x, y)

        event.accept()

    def update_visible_pages(self, current_page_index: int):
        """Load and display pages near the current page."""
        # Prevent re-entrant calls from scroll events during page loading
        if self._updating_pages:
            return

        if self.pdf_reader_core.doc is None or self.pdf_reader_core.total_pages == 0:
            return

        self._updating_pages = True

        try:
            if self.page_height is None:
                if current_page_index not in self.loaded_pages:
                    self._load_and_display_page(current_page_index)
                    if self.page_height is None:
                        return

            total_pages = self.pdf_reader_core.total_pages
            start_index = max(0, current_page_index - self.page_buffer)
            end_index = min(total_pages - 1, current_page_index + self.page_buffer)

            # Find and unload pages outside buffer
            pages_to_unload = [
                idx
                for idx in list(self.loaded_pages.keys())
                if idx < start_index or idx > end_index
            ]

            for idx in pages_to_unload:
                if idx in self.loaded_pages:
                    label = self.loaded_pages.pop(idx)
                    self._safely_delete_label(label)

                if idx in self.page_models:
                    self.page_models[idx].unload()
                    del self.page_models[idx]

            # Load missing pages
            for idx in range(start_index, end_index + 1):
                if idx not in self.loaded_pages:
                    self._load_and_display_page(idx)

            self.selection_manager.set_page_models(self.page_models)

        finally:
            self._updating_pages = False

    def _load_and_display_page(self, idx: int):
        """Render and display a single page."""
        if idx not in self.page_models:
            self.page_models[idx] = PageModel(self.pdf_reader_core.doc, idx)

        page_model = self.page_models[idx]
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
        QApplication.processEvents()

        label = InteractivePageLabel(
            page_model=page_model,
            zoom=self.zoom,
            selection_manager=self.selection_manager,
            parent=self.page_container,
        )

        label.set_dark_mode(self.dark_mode)
        label.set_annotations(annotations_on_page)
        label.link_handler = self.link_handler
        label.search_highlights = rects_on_page
        label.current_search_highlight_index = current_idx_on_page

        if (
            hasattr(self.main_window, "drawing_toolbar")
            and self.main_window.drawing_toolbar.is_in_drawing_mode()
        ):
            tool_settings = self.main_window.drawing_toolbar.get_current_settings()
            tool, color, stroke_width, filled = tool_settings
            label.set_drawing_mode(True, tool, color, stroke_width, filled)

        label.link_clicked.connect(self._on_link_clicked)
        label.selection_changed.connect(self._on_selection_changed)
        label.setAlignment(Qt.AlignCenter)

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

        container_width = self.page_container.width()
        pixmap = label.pixmap()
        if pixmap:
            x = (container_width - pixmap.width()) // 2
            y = idx * (self.page_height + self.page_spacing)
            label.setGeometry(x, y, pixmap.width(), pixmap.height())

        label.show()
        self.loaded_pages[idx] = label

        label.update()
        self.page_container.update()
        self.scroll_area.viewport().update()

    # ===== Navigation Methods =====

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
        """Scroll to a specific page position.

        Args:
            page_num: 1-based page number
            y_offset: Y-coordinate in top-left origin (already converted by _process_toc)
        """
        if self.page_height is None or self.page_height == 0:
            return

        if not (1 <= page_num <= self.pdf_reader_core.total_pages):
            return

        page_start_y = (page_num - 1) * (self.page_height + self.page_spacing)

        if y_offset > 0:
            try:
                page = self.pdf_reader_core.doc.load_page(page_num - 1)
                pdf_page_height = page.rect.height

                if y_offset <= pdf_page_height:
                    # y_offset is already in top-left coordinates
                    # Just normalize and scale to pixel space
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
        QTimer.singleShot(50, lambda: self.main_window.update_visible_pages())

    def jump_to_search_result(self, page_idx: int, rect_tuple):
        """Scroll to center on a search result."""
        if page_idx is None or rect_tuple is None:
            return

        if self.page_height is None:
            self._load_and_display_page(page_idx)
            if self.page_height is None:
                return

        self.update_visible_pages(page_idx)
        QApplication.processEvents()

        y0 = rect_tuple[1]
        height = (
            rect_tuple[5] if len(rect_tuple) > 5 else (rect_tuple[3] - rect_tuple[1])
        )

        viewport_height = self.scroll_area.viewport().height()
        scroll_offset = viewport_height / 2 - (height * self.zoom) / 2

        target_y = (
            (page_idx * (self.page_height + self.page_spacing))
            + (y0 * self.zoom)
            - scroll_offset
        )

        max_scroll = self.scroll_area.verticalScrollBar().maximum()
        target_y = max(0, min(int(target_y), max_scroll))

        self.scroll_area.verticalScrollBar().setValue(int(target_y))
        QTimer.singleShot(50, lambda: self._finish_search_jump(page_idx))

    def _finish_search_jump(self, page_idx: int):
        """Complete the search jump after scroll."""
        self.update_visible_pages(page_idx)
        self.update_page_highlights()

    def update_page_highlights(self):
        """Update search highlights on all loaded pages."""
        try:
            for idx, label in list(self.loaded_pages.items()):
                if not self._is_widget_valid(label):
                    continue

                rects_on_page = []
                current_idx_on_page = -1

                if hasattr(self.main_window, "search_engine"):
                    search_engine = self.main_window.search_engine
                    raw_rects, current_idx_on_page = (
                        SearchHighlight.get_highlights_for_page(search_engine, idx)
                    )

                    for r in raw_rects:
                        if hasattr(r, "x0"):
                            rects_on_page.append((r.x0, r.y0, r.x1, r.y1))
                        else:
                            rects_on_page.append(r)

                try:
                    label.search_highlights = rects_on_page
                    label.current_search_highlight_index = current_idx_on_page
                    label.update()
                except RuntimeError:
                    pass
        except Exception as e:
            print(f"HIGHLIGHT ERROR: {e}")
            import traceback

            traceback.print_exc()

    # ===== Selection Methods =====

    def copy_selected_text(self) -> str:
        """Get all selected text for copying."""
        return self.selection_manager.get_selected_text()

    def clear_selection(self):
        """Clear text selection."""
        self.selection_manager.clear()
        for label in list(self.loaded_pages.values()):
            if self._is_widget_valid(label):
                try:
                    label.update()
                except RuntimeError:
                    pass

    def select_all_on_page(self, page_index: int):
        """Select all text on a specific page."""
        self.selection_manager.select_all(page_index)
        if page_index in self.loaded_pages:
            label = self.loaded_pages[page_index]
            if self._is_widget_valid(label):
                try:
                    label.update()
                except RuntimeError:
                    pass

    # ===== Signal Handlers =====

    def _on_link_clicked(self, link):
        """Handle link click from page label."""
        pass

    def _on_navigation_requested(self, page_num: int, y_offset: float):
        """Handle navigation request from link handler."""
        self.jump_to_page(page_num, y_offset)

    def _on_selection_changed(self):
        """Handle selection change from page label."""
        for label in list(self.loaded_pages.values()):
            if self._is_widget_valid(label):
                try:
                    label.update()
                except RuntimeError:
                    pass

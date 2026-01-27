"""
PDF viewer widget - Fixed to use search engine.
"""
from PyQt5.QtCore import Qt
from ui.widgets.page_label import ClickablePageLabel
from core.search import SearchHighlight


class PDFViewer:
    def __init__(self, main_window, page_container_widget, scroll_area_widget, 
                 pdf_reader_core, annotation_manager):
        self.main_window = main_window
        self.page_container = page_container_widget
        self.scroll_area = scroll_area_widget
        self.pdf_reader_core = pdf_reader_core
        self.annotation_manager = annotation_manager
        
        # State inherited/shared from main window
        self.zoom = main_window.zoom
        self.dark_mode = main_window.dark_mode
        self.page_spacing = main_window.page_spacing
        self.loaded_pages = main_window.loaded_pages

        self.page_height = None
        
        self.page_container.setMinimumHeight(0)
        self.page_container.resizeEvent = self.container_resize_event

    def clear_all(self):
        """Clears all loaded pages and resets page state."""
        for label in self.loaded_pages.values():
            label.deleteLater()
        self.loaded_pages.clear()
        self.page_height = None
        self.page_container.setMinimumHeight(0)

    def set_zoom(self, new_zoom):
        """Updates the zoom factor for page rendering."""
        self.zoom = new_zoom

    def set_dark_mode(self, dark_mode):
        """Updates the dark mode setting for page rendering."""
        self.dark_mode = dark_mode

    def container_resize_event(self, event):
        """Repositions the page labels when the container size changes."""
        container_width = self.page_container.width()
        for idx, label in self.loaded_pages.items():
            if label.pixmap():
                pix_width = label.pixmap().width()
                x = (container_width - pix_width) // 2
                y = idx * (self.page_height + self.page_spacing)
                label.move(x, y)
        event.accept()

    def update_visible_pages(self, current_page_index):
        """
        Loads and displays pages that are currently visible or nearby.
        'current_page_index' is the page that is currently centered/focused.
        """
        if self.pdf_reader_core.doc is None or self.pdf_reader_core.total_pages == 0:
            return

        if self.page_height is None:
            if current_page_index not in self.loaded_pages:
                self._load_and_display_page(current_page_index)
                if self.page_height is None:
                    return
                
        total_pages = self.pdf_reader_core.total_pages
        start_index = max(0, current_page_index - 7)
        end_index = min(total_pages - 1, current_page_index + 7)
        
        # Unload pages outside the window
        for idx in list(self.loaded_pages.keys()):
            if idx < start_index or idx > end_index:
                self.loaded_pages[idx].deleteLater()
                del self.loaded_pages[idx]
        
        # Load missing pages within the window
        for idx in range(start_index, end_index + 1):
            if idx not in self.loaded_pages:
                self._load_and_display_page(idx)

    def _load_and_display_page(self, idx):
        """Renders a single page and creates its display label."""
        pix, text_data, word_data = self.pdf_reader_core.render_page(idx, self.zoom, self.dark_mode)
        if pix:
            # Get search highlights from the search engine
            rects_on_page = []
            current_idx_on_page = -1
            
            # Check if main window has search engine
            if hasattr(self.main_window, 'search_engine'):
                search_engine = self.main_window.search_engine
                rects_on_page, current_idx_on_page = SearchHighlight.get_highlights_for_page(
                    search_engine, idx
                )

            # Get annotations for this page
            annotations_on_page = self.annotation_manager.get_annotations_for_page(idx)

            label = ClickablePageLabel(self.page_container)
            label.set_page_data(
                pix, text_data, word_data, self.zoom, self.dark_mode, 
                search_highlights=rects_on_page, 
                current_highlight_index=current_idx_on_page,
                annotations=annotations_on_page
            )
            
            # Set drawing mode if active
            if hasattr(self.main_window, 'drawing_toolbar') and self.main_window.drawing_toolbar.is_in_drawing_mode():
                tool_settings = self.main_window.drawing_toolbar.get_current_settings()
                tool, color, stroke_width, filled = tool_settings
                label.set_drawing_mode(True, tool, color, stroke_width, filled)
            
            label.setAlignment(Qt.AlignCenter)
            
            if self.page_height is None:
                self.page_height = pix.height()
                total_height = (self.pdf_reader_core.total_pages * 
                                (self.page_height + self.page_spacing) - self.page_spacing)
                self.page_container.setMinimumHeight(total_height)
                self.main_window.page_height = self.page_height 
            
            container_width = self.page_container.width()
            x = (container_width - pix.width()) // 2
            y = idx * (self.page_height + self.page_spacing)
            label.setGeometry(x, y, pix.width(), pix.height())
            label.show()

            label.update()
            label.repaint()
            self.page_container.update()
            self.scroll_area.viewport().update()

            self.loaded_pages[idx] = label

    def get_current_page_index(self):
        """Calculates the index of the page currently centered in the viewport."""
        if self.page_height is None or self.page_height == 0:
            return 0
        
        vsb = self.scroll_area.verticalScrollBar()
        scroll_val = vsb.value()
        viewport_height = self.scroll_area.viewport().height()
        H = self.page_height + self.page_spacing
        
        current_page = round((scroll_val + viewport_height / 2 - self.page_height / 2) / H)
        current_page = max(0, min(self.pdf_reader_core.total_pages - 1, current_page))
        return current_page

    def get_scroll_info(self):
        """Returns the current page index and offset within that page for zoom adjustments."""
        if self.page_height is None or self.page_height == 0: 
            return 0, 0
        vsb = self.scroll_area.verticalScrollBar()
        scroll_val = vsb.value()
        H = self.page_height + self.page_spacing
        current_page_index = int(scroll_val / H)
        offset_in_page = scroll_val % H
        return current_page_index, offset_in_page

    def jump_to_page(self, page_num, y_offset=0.0):
        """
        Scrolls the viewport to a specific position on a page.
        page_num: 1-based page number
        y_offset: Y-coordinate on the page (in PDF coordinates)
        """
        if self.page_height is None or self.page_height == 0:
            return
            
        if not (1 <= page_num <= self.pdf_reader_core.total_pages):
            return
        
        # Calculate the page top position in viewport
        page_start_y = (page_num - 1) * (self.page_height + self.page_spacing)
        
        # If y_offset is provided and non-zero, try to use it
        if y_offset > 0:
            try:
                # Get the page to find its dimensions
                page = self.pdf_reader_core.doc.load_page(page_num - 1)
                page_rect = page.rect
                pdf_page_height = page_rect.height
                
                # Normalize the y_offset as a percentage of page height
                if y_offset <= pdf_page_height:
                    # y_offset from top
                    offset_from_top = y_offset
                    
                    # y_offset from bottom
                    offset_from_bottom = pdf_page_height - y_offset
                    
                    # Use the smaller offset
                    if offset_from_top <= pdf_page_height * 0.5:
                        normalized_offset = offset_from_top / pdf_page_height
                    else:
                        normalized_offset = offset_from_bottom / pdf_page_height
                else:
                    normalized_offset = 0.0
                
                # Apply the normalized offset to our rendered page
                pixel_offset = normalized_offset * self.page_height
                
                # Calculate target position
                viewport_height = self.scroll_area.viewport().height()
                target_y = page_start_y + pixel_offset - min(50, viewport_height * 0.1)
                target_y = max(0, target_y)
                
            except Exception as e:
                print(f"TOC navigation calculation failed: {e}")
                target_y = page_start_y
        else:
            target_y = page_start_y
        
        # Perform the scroll
        self.scroll_area.verticalScrollBar().setValue(int(target_y))
        
        # Update visible pages after scrolling
        if hasattr(self.main_window, 'update_visible_pages'):
            from PyQt5.QtCore import QTimer
            QTimer.singleShot(50, self.main_window.update_visible_pages)

    def update_page_highlights(self):
        """Updates the search highlights on all currently loaded pages."""
        for idx, label in self.loaded_pages.items():
            rects_on_page = []
            current_idx_on_page = -1
            
            # Get search highlights from search engine
            if hasattr(self.main_window, 'search_engine'):
                search_engine = self.main_window.search_engine
                rects_on_page, current_idx_on_page = SearchHighlight.get_highlights_for_page(
                    search_engine, idx
                )
            
            label.set_search_highlights(rects_on_page, current_idx_on_page)

    def jump_to_search_result(self, page_idx, rect):
        """Scrolls the view to center on a specific search result rectangle."""
        if page_idx is None or self.page_height is None or rect is None:
            return

        scroll_offset = self.scroll_area.height() / 2 - (rect.height * self.zoom) / 2
        target_y = (page_idx * (self.page_height + self.page_spacing)) + (rect.y0 * self.zoom) - scroll_offset
        
        self.scroll_area.verticalScrollBar().setValue(int(target_y))
        self.update_page_highlights()
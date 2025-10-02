from PyQt5.QtCore import Qt
from ui.page_label import ClickablePageLabel

class PDFViewer:
    def __init__(self, main_window, page_container_widget, scroll_area_widget, pdf_reader_core):
        self.main_window = main_window
        self.page_container = page_container_widget
        self.scroll_area = scroll_area_widget
        self.pdf_reader_core = pdf_reader_core # Assuming this is PDFDocumentReader
        
        # State inherited/shared from main window
        self.zoom = main_window.zoom
        self.dark_mode = main_window.dark_mode
        self.page_spacing = main_window.page_spacing
        self.loaded_pages = main_window.loaded_pages # Keep loaded_pages in the main window to be accessible there

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

        # Ensure the *current* page is loaded first, not just page 0
        if self.page_height is None:
            # Load the page the caller indicated (current_page_index), not always 0
            if current_page_index not in self.loaded_pages:
                self._load_and_display_page(current_page_index)
                if self.page_height is None:  # safety if render failed
                    return
                
        total_pages = self.pdf_reader_core.total_pages
        # Load a window of 15 pages around the current page (7 before, current, 7 after)
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
            # Prepare search highlight data for the page label
            search_results = self.pdf_reader_core.get_all_search_results()
            rects_on_page = [r for p, r in search_results if p == idx]
            current_idx_on_page = -1
            if (self.pdf_reader_core.current_search_index != -1 
                and search_results[self.pdf_reader_core.current_search_index][0] == idx):
                current_rect = search_results[self.pdf_reader_core.current_search_index][1]
                if current_rect in rects_on_page:
                    current_idx_on_page = rects_on_page.index(current_rect)

            label = ClickablePageLabel(self.page_container)
            label.set_page_data(
                pix, text_data, word_data, self.zoom, self.dark_mode, 
                search_highlights=rects_on_page, 
                current_highlight_index=current_idx_on_page
            )
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

            # Force immediate paint for the newly created label so it's visible
            label.update()
            label.repaint()
            # also nudge container and viewport
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
        
        # Calculate the page index that is closest to the center of the viewport
        current_page = round((scroll_val + viewport_height / 2 - self.page_height / 2) / H)
        current_page = max(0, min(self.pdf_reader_core.total_pages - 1, current_page))
        return current_page

    def get_scroll_info(self):
        """Returns the current page index and offset within that page for zoom adjustments."""
        if self.page_height is None or self.page_height == 0: return 0, 0
        vsb = self.scroll_area.verticalScrollBar()
        scroll_val = vsb.value()
        H = self.page_height + self.page_spacing
        current_page_index = int(scroll_val / H)
        offset_in_page = scroll_val % H
        return current_page_index, offset_in_page

    def jump_to_page(self, page_num):
        """Scrolls the viewport to the beginning of the specified page number (1-based)."""
        if self.page_height is None or self.page_height == 0: return
        if 1 <= page_num <= self.pdf_reader_core.total_pages:
            target_y = (page_num - 1) * (self.page_height + self.page_spacing)
            self.scroll_area.verticalScrollBar().setValue(int(target_y))

    def update_page_highlights(self):
        """Updates the search highlights on all currently loaded pages."""
        for idx, label in self.loaded_pages.items():
            search_results = self.pdf_reader_core.get_all_search_results()
            rects_on_page = [r for p, r in search_results if p == idx]
            current_idx_on_page = -1
            if self.pdf_reader_core.current_search_index != -1:
                current_page, current_rect = search_results[self.pdf_reader_core.current_search_index]
                if current_page == idx and current_rect in rects_on_page:
                    current_idx_on_page = rects_on_page.index(current_rect)
            
            label.set_search_highlights(rects_on_page, current_idx_on_page)

    def jump_to_search_result(self, page_idx, rect):
        """Scrolls the view to center on a specific search result rectangle."""
        if page_idx is None or self.page_height is None:
            return

        scroll_offset = self.scroll_area.height() / 2 - (rect.height * self.zoom) / 2
        target_y = (page_idx * (self.page_height + self.page_spacing)) + (rect.y0 * self.zoom) - scroll_offset
        
        self.scroll_area.verticalScrollBar().setValue(int(target_y))
        self.update_page_highlights()
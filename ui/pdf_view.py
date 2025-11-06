from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import QWidget, QVBoxLayout

class PDFViewer:
    def __init__(self, main_window, page_container_widget, scroll_area_widget, pdf_reader_core, annotation_manager):
        self.main_window = main_window
        self.page_container = page_container_widget
        self.scroll_area = scroll_area_widget
        self.pdf_reader_core = pdf_reader_core  # Now using EnhancedPDFReader
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
        for widget in self.loaded_pages.values():
            widget.deleteLater()
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
        """Repositions the page widgets when the container size changes."""
        container_width = self.page_container.width()
        for idx, widget in self.loaded_pages.items():
            widget_width = widget.width()
            x = (container_width - widget_width) // 2
            y = idx * (self.page_height + self.page_spacing)
            widget.move(x, y)
        event.accept()

    def update_visible_pages(self, current_page_index):
        """
        Loads and displays pages that are currently visible or nearby.
        'current_page_index' is the page that is currently centered/focused.
        """
        if self.pdf_reader_core.doc is None or self.pdf_reader_core.total_pages == 0:
            return

        # Load first page to get height if needed
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
        """Renders page using PyMuPDF and extracts elements for interaction."""
        # Render page to pixmap using PyMuPDF
        page_pixmap = self.pdf_reader_core.render_page(idx, self.zoom, self.dark_mode)
        
        if not page_pixmap:
            return
        
        # Get parsed page elements for selection and links
        page_elements = self.pdf_reader_core.get_page_elements(idx, use_cache=True)
        
        if not page_elements:
            return
        
        # Get search highlights for this page
        search_results = self.pdf_reader_core.get_all_search_results()
        rects_on_page = [r for p, r in search_results if p == idx]
        current_idx_on_page = -1
        if (self.pdf_reader_core.current_search_index != -1 
            and search_results[self.pdf_reader_core.current_search_index][0] == idx):
            current_rect = search_results[self.pdf_reader_core.current_search_index][1]
            if current_rect in rects_on_page:
                current_idx_on_page = rects_on_page.index(current_rect)

            # Get annotations for this page
            annotations_on_page = self.annotation_manager.get_annotations_for_page(idx)
            
            # Get the PDF page object for link extraction
            pdf_page = self.pdf_reader_core.doc.load_page(idx) if self.pdf_reader_core.doc else None

            label = ClickablePageLabel(self.page_container)
            label.set_page_data(
                pix, text_data, word_data, self.zoom, self.dark_mode, 
                search_highlights=rects_on_page, 
                current_highlight_index=current_idx_on_page,
                annotations=annotations_on_page,
                page_index=idx,
                pdf_page=pdf_page  # Pass the page object for link extraction
            )
            
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

        # Force updates
        widget.update()
        widget.repaint()
        self.page_container.update()
        self.scroll_area.viewport().update()

        self.loaded_pages[idx] = widget

    def _on_link_clicked(self, link_type, destination):
        """Handle link clicks from page widgets."""
        if link_type == "goto" and destination is not None:
            # Internal link - jump to page
            self.jump_to_page(destination + 1)  # Convert to 1-based
        elif link_type == "uri" and destination:
            # External link - open in browser
            import webbrowser
            webbrowser.open(destination)

    def _on_text_selection_changed(self, selected_text):
        """Handle text selection changes from page widgets."""
        # Store selected text for copy operations
        if hasattr(self.main_window, 'current_selected_text'):
            self.main_window.current_selected_text = selected_text

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
        y_offset: Y-coordinate on the page (in PDF's native coordinates, origin at bottom-left)
        """
        if self.page_height is None or self.page_height == 0:
            return
        if 1 <= page_num <= self.pdf_reader_core.total_pages:
            # Get the page to find its height in PDF coordinates
            page_elements = self.pdf_reader_core.get_page_elements(page_num - 1)
            if not page_elements:
                return
            
            pdf_page_height = page_elements.height
            
            # PDF coordinates have origin at bottom-left, but rendering has origin at top-left
            # So we need to flip the y-coordinate
            flipped_y = pdf_page_height - y_offset
            
            # Calculate the target scroll position
            page_start_y = (page_num - 1) * (self.page_height + self.page_spacing)
            
            # Scale the flipped offset to match our current zoom level
            scaled_offset = flipped_y * self.zoom
            
            target_y = page_start_y + scaled_offset
            self.scroll_area.verticalScrollBar().setValue(int(target_y))

    def update_page_highlights(self):
        """Updates the search highlights on all currently loaded pages."""
        for idx, widget in self.loaded_pages.items():
            search_results = self.pdf_reader_core.get_all_search_results()
            rects_on_page = [r for p, r in search_results if p == idx]
            current_idx_on_page = -1
            if self.pdf_reader_core.current_search_index != -1:
                current_page, current_rect = search_results[self.pdf_reader_core.current_search_index]
                if current_page == idx and current_rect in rects_on_page:
                    current_idx_on_page = rects_on_page.index(current_rect)
            
            # Update widget's search highlights
            page_elements = self.pdf_reader_core.get_page_elements(idx)
            annotations_on_page = self.annotation_manager.get_annotations_for_page(idx)
            
            widget.set_page_data(
                page_pixmap=widget.page_pixmap,  # <-- THIS IS THE FIX
                page_elements=page_elements,
                page_index=idx,
                zoom_level=self.zoom,
                dark_mode=self.dark_mode,
                search_highlights=rects_on_page,
                current_highlight_index=current_idx_on_page,
                annotations=annotations_on_page
            )

    def jump_to_search_result(self, page_idx, rect):
        """Scrolls the view to center on a specific search result rectangle."""
        if page_idx is None or self.page_height is None:
            return

        scroll_offset = self.scroll_area.height() / 2 - (rect.height * self.zoom) / 2
        target_y = (page_idx * (self.page_height + self.page_spacing)) + (rect.y0 * self.zoom) - scroll_offset
        
        self.scroll_area.verticalScrollBar().setValue(int(target_y))
        self.update_page_highlights()

    def get_selected_text_from_current_page(self):
        """Get selected text from the currently focused page."""
        current_page_idx = self.get_current_page_index()
        if current_page_idx in self.loaded_pages:
            widget = self.loaded_pages[current_page_idx]
            return widget._get_selected_text()
        return ""

    def clear_all_selections(self):
        """Clear text selection on all loaded pages."""
        for widget in self.loaded_pages.values():
            widget.clear_selection()
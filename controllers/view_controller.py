"""
Controller for managing PDF view operations and page navigation.
"""
import fitz  # PyMuPDF
from typing import Optional, Dict, Tuple
from PyQt5.QtCore import QObject, pyqtSignal, QTimer
from PyQt5.QtWidgets import QScrollArea, QWidget


class ViewController(QObject):
    """Manages view state and page navigation for the PDF viewer."""
    
    # Signals
    page_changed = pyqtSignal(int)  # Emitted when current page changes
    zoom_changed = pyqtSignal(float)  # Emitted when zoom level changes
    
    def __init__(self, scroll_area: QScrollArea, page_container: QWidget):
        super().__init__()
        
        self.scroll_area = scroll_area
        self.page_container = page_container
        
        # View state
        self.current_page: int = 0
        self.zoom_level: float = 2.2
        self.base_zoom: float = 2.2
        self.page_height: Optional[int] = None
        self.page_spacing: int = 30
        self.total_pages: int = 0
        
        # Loaded pages tracking
        self.loaded_pages: Dict[int, QWidget] = {}
        
        # Connect scroll events
        self.scroll_area.verticalScrollBar().valueChanged.connect(self._on_scroll)
    
    def set_document_info(self, total_pages: int) -> None:
        """
        Set document information for view calculations.
        
        Args:
            total_pages: Total number of pages in the document
        """
        self.total_pages = total_pages
        self.current_page = 0
        self.page_height = None
        self.loaded_pages.clear()
    
    def set_page_height(self, height: int) -> None:
        """
        Set the height of pages for scroll calculations.
        
        Args:
            height: Height of a rendered page in pixels
        """
        if self.page_height != height:
            self.page_height = height
            self._update_container_height()
    
    def _update_container_height(self) -> None:
        """Update the container height based on total pages."""
        if self.page_height and self.total_pages > 0:
            total_height = (self.total_pages * 
                          (self.page_height + self.page_spacing) - 
                          self.page_spacing)
            self.page_container.setMinimumHeight(total_height)
    
    def get_current_page(self) -> int:
        """
        Calculate the currently visible page.
        
        Returns:
            0-based index of the current page
        """
        if not self.page_height or self.page_height == 0:
            return 0
        
        vsb = self.scroll_area.verticalScrollBar()
        scroll_val = vsb.value()
        viewport_height = self.scroll_area.viewport().height()
        
        # Calculate which page is in the center of the viewport
        center_y = scroll_val + viewport_height / 2
        page_with_spacing = self.page_height + self.page_spacing
        
        current = int(center_y / page_with_spacing)
        return max(0, min(self.total_pages - 1, current))
    
    def get_visible_page_range(self, buffer_pages: int = 7) -> Tuple[int, int]:
        """
        Get the range of pages that should be loaded.
        
        Args:
            buffer_pages: Number of pages to load above/below visible area
            
        Returns:
            Tuple of (start_index, end_index) inclusive
        """
        if self.total_pages == 0:
            return 0, 0
        
        current = self.get_current_page()
        start = max(0, current - buffer_pages)
        end = min(self.total_pages - 1, current + buffer_pages)
        
        return start, end
    
    def jump_to_page(self, page_num: int, y_offset: float = 0.0) -> None:
        """
        Jump to a specific page.
        
        Args:
            page_num: 1-based page number
            y_offset: Optional Y-offset within the page
        """
        if not self.page_height or self.page_height == 0:
            return
        
        if not (1 <= page_num <= self.total_pages):
            return
        
        # Calculate scroll position
        page_idx = page_num - 1
        page_start_y = page_idx * (self.page_height + self.page_spacing)
        
        if y_offset > 0:
            # Apply offset if provided
            viewport_height = self.scroll_area.viewport().height()
            target_y = page_start_y + (y_offset * self.zoom_level) - min(50, viewport_height * 0.1)
            target_y = max(0, target_y)
        else:
            target_y = page_start_y
        
        self.scroll_area.verticalScrollBar().setValue(int(target_y))
    
    def jump_to_rect(self, page_idx: int, rect: fitz.Rect) -> None:
        """
        Jump to a specific rectangle on a page.
        
        Args:
            page_idx: 0-based page index
            rect: Rectangle to center in view
        """
        if not self.page_height or page_idx < 0:
            return
        
        # Calculate position to center the rect
        viewport_height = self.scroll_area.height()
        rect_center_y = rect.y0 + (rect.height / 2)
        
        page_y = page_idx * (self.page_height + self.page_spacing)
        rect_y = rect_center_y * self.zoom_level
        
        # Center the rect in viewport
        target_y = page_y + rect_y - (viewport_height / 2)
        target_y = max(0, target_y)
        
        self.scroll_area.verticalScrollBar().setValue(int(target_y))
    
    def get_scroll_position(self) -> Tuple[int, int]:
        """
        Get current scroll position for zoom operations.
        
        Returns:
            Tuple of (page_index, offset_in_page)
        """
        if not self.page_height or self.page_height == 0:
            return 0, 0
        
        vsb = self.scroll_area.verticalScrollBar()
        scroll_val = vsb.value()
        
        page_with_spacing = self.page_height + self.page_spacing
        page_idx = int(scroll_val / page_with_spacing)
        offset = scroll_val % page_with_spacing
        
        return page_idx, offset
    
    def restore_scroll_position(self, page_idx: int, offset: int) -> None:
        """
        Restore scroll position after zoom change.
        
        Args:
            page_idx: Page index from get_scroll_position
            offset: Offset from get_scroll_position
        """
        if self.page_height:
            target_y = (page_idx * (self.page_height + self.page_spacing)) + offset
            self.scroll_area.verticalScrollBar().setValue(int(target_y))
    
    def set_zoom(self, zoom_percent: int) -> None:
        """
        Set zoom level as percentage.
        
        Args:
            zoom_percent: Zoom percentage (100 = base zoom)
        """
        self.zoom_level = (zoom_percent / 100.0) * self.base_zoom
        self.zoom_changed.emit(self.zoom_level)
    
    def get_zoom_percent(self) -> int:
        """
        Get current zoom as percentage.
        
        Returns:
            Zoom percentage
        """
        return int((self.zoom_level / self.base_zoom) * 100)
    
    def adjust_zoom(self, delta: int) -> int:
        """
        Adjust zoom by delta percentage.
        
        Args:
            delta: Percentage change (+/- value)
            
        Returns:
            New zoom percentage
        """
        current = self.get_zoom_percent()
        new_zoom = max(20, min(300, current + delta))
        self.set_zoom(new_zoom)
        return new_zoom
    
    def register_loaded_page(self, page_idx: int, widget: QWidget) -> None:
        """
        Register a loaded page widget.
        
        Args:
            page_idx: Page index
            widget: Page widget
        """
        self.loaded_pages[page_idx] = widget
    
    def unregister_page(self, page_idx: int) -> None:
        """
        Unregister a page widget.
        
        Args:
            page_idx: Page index to unregister
        """
        if page_idx in self.loaded_pages:
            del self.loaded_pages[page_idx]
    
    def get_loaded_page(self, page_idx: int) -> Optional[QWidget]:
        """
        Get a loaded page widget.
        
        Args:
            page_idx: Page index
            
        Returns:
            Page widget or None
        """
        return self.loaded_pages.get(page_idx)
    
    def clear_all_pages(self) -> None:
        """Clear all loaded pages."""
        self.loaded_pages.clear()
        self.page_height = None
        self.page_container.setMinimumHeight(0)
    
    def _on_scroll(self, value: int) -> None:
        """Handle scroll events."""
        new_page = self.get_current_page()
        if new_page != self.current_page:
            self.current_page = new_page
            self.page_changed.emit(new_page)
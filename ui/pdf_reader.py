from PyQt5.QtCore import Qt, QPoint, QRect, QRectF
from PyQt5.QtGui import QImage, QPixmap, QIntValidator, QPainter, QColor, QKeySequence
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QFileDialog, QScrollArea, QLineEdit, QFrame,
    QMessageBox
)
import fitz  # PyMuPDF
import sys
from styles.styles import apply_style
import pyperclip

# Custom widget to display a page image and handle text selection
class ClickablePageLabel(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.text_data = None  # Stores the text blocks, lines, and spans
        self.word_data = None  # New: Stores word-level data from PyMuPDF
        self.zoom_level = 1.0
        self.start_pos = None
        self.end_pos = None
        self.selection_rects = []
        self.dark_mode = False # Tracks the mode for selection color
        self.setMouseTracking(True) # To allow selection highlighting

    def set_page_data(self, pixmap, text_data, word_data, zoom_level, dark_mode):
        """Sets the page image, text data, and zoom level."""
        self.setPixmap(pixmap)
        self.text_data = text_data
        self.word_data = word_data
        self.zoom_level = zoom_level
        self.dark_mode = dark_mode
        self.selection_rects = []
        self.update() # Repaint the widget

    def mousePressEvent(self, event):
        """Records the starting position for a new text selection."""
        if event.button() == Qt.LeftButton:
            self.start_pos = event.pos()
            self.end_pos = None
            self.selection_rects = []
            self.update()

    def mouseMoveEvent(self, event):
        """Updates the end position as the user drags and highlights text."""
        if event.buttons() & Qt.LeftButton and self.word_data:
            self.end_pos = event.pos()
            self.selection_rects = self.get_selection_rects()
            self.update()
        
    def mouseReleaseEvent(self, event):
        """Finalizes the selection on mouse button release."""
        if event.button() == Qt.LeftButton and self.word_data:
            self.end_pos = event.pos()
            self.selection_rects = self.get_selection_rects()
            self.update()

    def paintEvent(self, event):
        """Draws the page image and then overlays the selection highlight."""
        super().paintEvent(event)
        if self.selection_rects:
            painter = QPainter(self)
            painter.setPen(Qt.NoPen)
            # Change selection color based on dark mode
            if self.dark_mode:
                painter.setBrush(QColor(255, 255, 0, 128)) # Yellow for dark mode
            else:
                painter.setBrush(QColor(0, 0, 255, 100)) # Blue for light mode
            for rect in self.selection_rects:
                painter.drawRect(rect)
            painter.end()

    def get_selection_rects(self):
        """
        Calculates the rectangles to highlight based on the mouse selection area.
        This now operates on a word-by-word basis.
        """
        if not self.start_pos or not self.end_pos or not self.word_data:
            return []

        rects = []
        selection_rect = QRect(self.start_pos, self.end_pos).normalized()
        
        # Iterate over the word data (PyMuPDF returns a tuple: (x0, y0, x1, y1, word, block_no, line_no, word_no))
        for word_info in self.word_data:
            bbox = word_info[:4]
            word_rect = QRectF(
                bbox[0] * self.zoom_level,
                bbox[1] * self.zoom_level,
                (bbox[2] - bbox[0]) * self.zoom_level,
                (bbox[3] - bbox[1]) * self.zoom_level
            ).toRect()
            
            if selection_rect.intersects(word_rect):
                rects.append(word_rect)
        return rects
    
    def get_selected_text(self):
        """
        Extracts the actual text string from the selected words.
        """
        if not self.start_pos or not self.end_pos or not self.word_data:
            return ""

        selected_words = []
        selection_rect = QRect(self.start_pos, self.end_pos).normalized()

        for word_info in self.word_data:
            bbox = word_info[:4]
            word_rect = QRectF(
                bbox[0] * self.zoom_level,
                bbox[1] * self.zoom_level,
                (bbox[2] - bbox[0]) * self.zoom_level,
                (bbox[3] - bbox[1]) * self.zoom_level
            ).toRect()
            
            if selection_rect.intersects(word_rect):
                selected_words.append(word_info[4]) # The fifth element is the word text
        
        return " ".join(selected_words)

class PDFReader(QMainWindow):
    def __init__(self, file_path=None):
        """
        Initializes the PDF reader window.
        
        Args:
            file_path (str, optional): The path to a PDF file to open on startup.
        """
        super().__init__()
        self.setWindowTitle("PDF Reader")
        
        # Document state
        self.doc = None
        self.total_pages = 0
        # Internal zoom level used for rendering. 
        self.zoom = 2.2
        # Base zoom factor, mapping 2.2 to the displayed 100%.
        self.base_zoom = 2.2
        self.dark_mode = True  # Dark mode enabled by default
        self.page_spacing = 30  # Space between pages
        self.page_height = None  # Will be set after rendering the first page
        # Now stores instances of our custom ClickablePageLabel
        self.loaded_pages = {}
        self.current_page_index = 0
        
        self.setup_ui()
        self.apply_style()
        self.showMaximized()  # Open in windowed fullscreen mode

        if file_path:
            self.load_pdf(file_path)

    def setup_ui(self):
        """Initializes and lays out the UI components."""
        # -----------------------------
        #         TOP TOOLBAR
        # -----------------------------
        self.top_frame = QFrame()
        self.top_frame.setObjectName("TopFrame")
        self.top_layout = QHBoxLayout(self.top_frame)
        self.top_layout.setContentsMargins(5, 5, 5, 5)
        self.top_layout.setSpacing(10)
        
        # Page number controls
        self.top_layout.addWidget(QLabel("Page:", self.top_frame))
        self.page_edit = QLineEdit("1", self.top_frame)
        self.page_edit.setFixedWidth(50)
        self.page_edit.returnPressed.connect(self.page_number_changed)
        self.top_layout.addWidget(self.page_edit)
        
        self.total_page_label = QLabel("/ 0", self.top_frame)
        self.top_layout.addWidget(self.total_page_label)
        
        # Open PDF button
        self.open_button = QPushButton("Open PDF", self.top_frame)
        self.open_button.clicked.connect(self.open_pdf)
        self.top_layout.addWidget(self.open_button)
        
        # Dark Mode toggle
        self.toggle_button = QPushButton("Toggle Dark Mode", self.top_frame)
        self.toggle_button.clicked.connect(self.toggle_mode)
        self.top_layout.addWidget(self.toggle_button)
        
        # Zoom controls
        self.top_layout.addWidget(QLabel("Zoom:", self.top_frame))
        self.zoom_lineedit = QLineEdit("100", self.top_frame)
        self.zoom_lineedit.setFixedWidth(50)
        self.zoom_lineedit.setValidator(QIntValidator(20, 300, self))
        self.zoom_lineedit.returnPressed.connect(self.manual_zoom_changed)
        self.top_layout.addWidget(self.zoom_lineedit)
        
        self.plus_button = QPushButton("+", self.top_frame)
        self.plus_button.clicked.connect(lambda: self.adjust_zoom(20))
        self.top_layout.addWidget(self.plus_button)
        
        self.minus_button = QPushButton("–", self.top_frame)
        self.minus_button.clicked.connect(lambda: self.adjust_zoom(-20))
        self.top_layout.addWidget(self.minus_button)
        
        # -----------------------------
        #      PAGE DISPLAY AREA
        # -----------------------------
        # The container uses no layout – pages will be absolutely positioned.
        self.page_container = QWidget()
        self.page_container.setMinimumHeight(0)
        self.page_container.resizeEvent = self.container_resize_event
        
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setWidget(self.page_container)
        self.scroll_area.verticalScrollBar().valueChanged.connect(self.on_scroll)
        
        # -----------------------------
        #         MAIN LAYOUT
        # -----------------------------
        main_layout = QVBoxLayout()
        main_layout.addWidget(self.top_frame)
        main_layout.addWidget(self.scroll_area)
        container = QWidget()
        container.setLayout(main_layout)
        self.setCentralWidget(container)
        
    def keyPressEvent(self, event):
        """Handle keyboard shortcuts."""
        # Check for Ctrl+C
        if event.matches(QKeySequence.Copy):
            self.copy_selected_text()
            event.accept()
        else:
            super().keyPressEvent(event)

    def apply_style(self):
        """Apply style sheets based on dark mode."""
        apply_style(self, self.dark_mode)
    
    def copy_selected_text(self):
        """Copies the selected text from the current page to the clipboard."""
        if self.doc is None or self.current_page_index not in self.loaded_pages:
            QMessageBox.warning(self, "No Page Loaded", "Please load a PDF document first.")
            return

        current_page_widget = self.loaded_pages[self.current_page_index]
        selected_text = current_page_widget.get_selected_text()
        
        if selected_text:
            try:
                # Using pyperclip for cross-platform clipboard support
                pyperclip.copy(selected_text)
                QMessageBox.information(self, "Success", "Selected text copied to clipboard!")
            except pyperclip.PyperclipException as e:
                # Fallback or user info for platforms without a clipboard
                QMessageBox.warning(self, "Copy Error", f"Could not copy text: {e}. Please install xclip or xsel for Linux, or try again.")
        else:
            QMessageBox.information(self, "No Selection", "No text has been selected on the current page.")
            
    def container_resize_event(self, event):
        """Center all loaded pages horizontally in the container."""
        container_width = self.page_container.width()
        for idx, label in self.loaded_pages.items():
            if label.pixmap():
                pix_width = label.pixmap().width()
                x = (container_width - pix_width) // 2
                y = idx * (self.page_height + self.page_spacing)
                label.move(x, y)
        event.accept()
    
    def open_pdf(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Open PDF", "", "PDF Files (*.pdf)")
        if file_path:
            self.load_pdf(file_path)
    
    def load_pdf(self, file_path):
        try:
            self.doc = fitz.open(file_path)
            self.total_pages = self.doc.page_count
            self.total_page_label.setText(f"/ {self.total_pages}")
            self.page_edit.setValidator(QIntValidator(1, self.total_pages, self))
            self.clear_loaded_pages()
            self.page_height = None  # Reset page height for new document
            self.update_visible_pages()  # Load initial pages
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error loading PDF: {e}")
    
    def clear_loaded_pages(self):
        """Remove all loaded page widgets."""
        for label in self.loaded_pages.values():
            label.deleteLater()
        self.loaded_pages.clear()
    
    def render_page(self, page_index):
        """
        Render a single page and extract text data.
        Returns a tuple of (QPixmap, text_data, word_data).
        """
        try:
            page = self.doc.load_page(page_index)
            mat = fitz.Matrix(self.zoom, self.zoom)
            
            # Get the page image
            pix = page.get_pixmap(matrix=mat)
            img = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format_RGB888)
            if self.dark_mode:
                img.invertPixels()
            pixmap = QPixmap.fromImage(img)
            
            # Get the text and word data
            text_data = page.get_text("dict", sort=True)
            word_data = page.get_text("words", sort=True)

            if self.page_height is None:
                # Set the page height and update container height
                self.page_height = pixmap.height()
                total_height = self.total_pages * (self.page_height + self.page_spacing) - self.page_spacing
                self.page_container.setMinimumHeight(total_height)
                
            return pixmap, text_data, word_data
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error rendering page {page_index+1}: {e}")
            return None, None, None
    
    def update_visible_pages(self):
        """
        Lazy-load pages so that only the window [current-7, current+7] is loaded.
        Pages outside this range are removed.
        """
        if self.doc is None or self.total_pages == 0:
            return

        # If no page has been rendered yet, force-render page 0 to initialize page_height.
        if self.page_height is None:
            pix, text_data, word_data = self.render_page(0)
            if pix:
                label = ClickablePageLabel(self.page_container)
                # Pass the dark_mode state to the page label
                label.set_page_data(pix, text_data, word_data, self.zoom, self.dark_mode)
                label.setAlignment(Qt.AlignCenter)
                container_width = self.page_container.width()
                x = (container_width - pix.width()) // 2
                y = 0
                label.setGeometry(x, y, pix.width(), pix.height())
                label.show()
                self.loaded_pages[0] = label

        vsb = self.scroll_area.verticalScrollBar()
        scroll_val = vsb.value()
        viewport_height = self.scroll_area.viewport().height()
        if self.page_height is None or self.page_height == 0:
            return
            
        H = self.page_height + self.page_spacing
        current_page = round((scroll_val + viewport_height / 2 - self.page_height / 2) / H)
        current_page = max(0, min(self.total_pages - 1, current_page))
        self.current_page_index = current_page
        
        start_index = max(0, current_page - 7)
        end_index = min(self.total_pages - 1, current_page + 7)
        
        # Remove pages outside the window
        for idx in list(self.loaded_pages.keys()):
            if idx < start_index or idx > end_index:
                self.loaded_pages[idx].deleteLater()
                del self.loaded_pages[idx]
        
        # Load pages in the window if not already loaded
        for idx in range(start_index, end_index + 1):
            if idx not in self.loaded_pages:
                pix, text_data, word_data = self.render_page(idx)
                if pix:
                    label = ClickablePageLabel(self.page_container)
                    # Pass the dark_mode state to the page label
                    label.set_page_data(pix, text_data, word_data, self.zoom, self.dark_mode)
                    label.setAlignment(Qt.AlignCenter)
                    container_width = self.page_container.width()
                    x = (container_width - pix.width()) // 2
                    y = idx * (self.page_height + self.page_spacing)
                    label.setGeometry(x, y, pix.width(), pix.height())
                    label.show()
                    self.loaded_pages[idx] = label
    
    def update_current_page_display(self):
        """
        Updates the current page number display based on the scroll position.
        """
        if self.page_height is None:
            return
        vsb = self.scroll_area.verticalScrollBar()
        scroll_val = vsb.value()
        viewport_height = self.scroll_area.viewport().height()
        H = self.page_height + self.page_spacing
        current_page = round((scroll_val + viewport_height / 2 - self.page_height / 2) / H)
        current_page = max(0, min(self.total_pages - 1, current_page))
        if not self.page_edit.hasFocus():
            self.page_edit.setText(str(current_page + 1))
    
    def on_scroll(self):
        """Called whenever the user scrolls. Update visible pages and the page number."""
        self.update_visible_pages()
        self.update_current_page_display()
    
    def page_number_changed(self):
        """Scroll to the page specified by the user."""
        if self.page_height is None:
            return
        try:
            page_num = int(self.page_edit.text())
            if 1 <= page_num <= self.total_pages:
                target_y = (page_num - 1) * (self.page_height + self.page_spacing)
                vsb = self.scroll_area.verticalScrollBar()
                vsb.setValue(target_y)
            else:
                self.page_edit.setText(str(self.current_page_index + 1))
        except (ValueError, IndexError):
            self.page_edit.setText(str(self.current_page_index + 1))

    def get_current_page_info(self):
        """
        Returns the current page index and the scroll offset within that page.
        """
        if self.page_height is None or self.page_height == 0:
            return 0, 0
        
        vsb = self.scroll_area.verticalScrollBar()
        scroll_val = vsb.value()
        H = self.page_height + self.page_spacing
        current_page_index = int(scroll_val / H)
        offset_in_page = scroll_val % H
        return current_page_index, offset_in_page
    
    def manual_zoom_changed(self):
        """Update zoom level when the user enters a new value."""
        try:
            current_page_index, offset_in_page = self.get_current_page_info()
            
            value = int(self.zoom_lineedit.text())
            # Convert the displayed percentage to the internal zoom factor
            self.zoom = (value / 100.0) * self.base_zoom
            
            if self.doc:
                self.clear_loaded_pages()
                self.page_height = None
                self.update_visible_pages()
                
                # Calculate new scroll position based on the old offset
                new_scroll_pos = current_page_index * (self.page_height + self.page_spacing) + offset_in_page
                self.scroll_area.verticalScrollBar().setValue(new_scroll_pos)
                
        except (ValueError, IndexError):
            # Display the current percentage if the input is invalid
            current_zoom_percent = int((self.zoom / self.base_zoom) * 100)
            self.zoom_lineedit.setText(str(current_zoom_percent))
    
    def adjust_zoom(self, delta):
        """Adjust zoom level via plus/minus buttons."""
        try:
            current_page_index, offset_in_page = self.get_current_page_info()
            
            # Calculate the new displayed percentage
            new_zoom_percent = int((self.zoom / self.base_zoom) * 100) + delta
            new_zoom_percent = max(20, min(300, new_zoom_percent))
            self.zoom_lineedit.setText(str(new_zoom_percent))
            
            # Convert the new displayed percentage to the internal zoom factor
            self.zoom = (new_zoom_percent / 100.0) * self.base_zoom
            
            if self.doc:
                self.clear_loaded_pages()
                self.page_height = None
                self.update_visible_pages()
                
                # Calculate new scroll position
                new_scroll_pos = current_page_index * (self.page_height + self.page_spacing) + offset_in_page
                self.scroll_area.verticalScrollBar().setValue(new_scroll_pos)
        except Exception as e:
            print(f"Error adjusting zoom: {e}")
    
    def toggle_mode(self):
        """Toggle between dark and light mode."""
        self.dark_mode = not self.dark_mode
        self.apply_style()
        if self.doc:
            self.clear_loaded_pages()
            self.page_height = None
            self.update_visible_pages()
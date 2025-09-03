from PyQt5.QtCore import Qt
from PyQt5.QtGui import QImage, QPixmap, QIntValidator
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QFileDialog, QScrollArea, QLineEdit, QFrame
)
import fitz  # PyMuPDF
from styles.styles import apply_style


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
        self.zoom = 2.2  # 220% zoom by default
        self.dark_mode = True  # Dark mode enabled by default
        self.page_spacing = 30  # Space between pages
        self.page_height = None  # Will be set after rendering the first page
        self.loaded_pages = {}  # Dictionary mapping page index -> QLabel
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
        self.zoom_lineedit = QLineEdit("220", self.top_frame)
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

    def apply_style(self):
        """Apply style sheets based on dark mode."""
        apply_style(self, self.dark_mode)

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
            print(f"Error loading PDF: {e}")
    
    def clear_loaded_pages(self):
        """Remove all loaded page widgets."""
        for label in self.loaded_pages.values():
            label.deleteLater()
        self.loaded_pages.clear()
    
    def render_page(self, page_index):
        """Render a single page and return a QPixmap."""
        try:
            page = self.doc.load_page(page_index)
            mat = fitz.Matrix(self.zoom, self.zoom)
            pix = page.get_pixmap(matrix=mat)
            img = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format_RGB888)
            if self.dark_mode:
                img.invertPixels()
            pixmap = QPixmap.fromImage(img)
            if self.page_height is None:
                # Set the page height and update container height
                self.page_height = pixmap.height()
                total_height = self.total_pages * (self.page_height + self.page_spacing) - self.page_spacing
                self.page_container.setMinimumHeight(total_height)
            return pixmap
        except Exception as e:
            print(f"Error rendering page {page_index+1}: {e}")
            return None
    
    def update_visible_pages(self):
        """
        Lazy-load pages so that only the window [current-7, current+7] is loaded.
        Pages outside this range are removed.
        """
        if self.doc is None or self.total_pages == 0:
            return

        # If no page has been rendered yet, force-render page 0 to initialize page_height.
        if self.page_height is None:
            pix = self.render_page(0)
            if pix:
                label = QLabel(self.page_container)
                label.setPixmap(pix)
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
                pix = self.render_page(idx)
                if pix:
                    label = QLabel(self.page_container)
                    label.setPixmap(pix)
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
            self.zoom = value / 100.0
            
            if self.doc:
                self.clear_loaded_pages()
                self.page_height = None
                self.update_visible_pages()
                
                # Calculate new scroll position
                new_scroll_pos = current_page_index * (self.page_height + self.page_spacing) + offset_in_page
                self.scroll_area.verticalScrollBar().setValue(new_scroll_pos)
                
        except (ValueError, IndexError):
            self.zoom_lineedit.setText(str(int(self.zoom * 100)))
    
    def adjust_zoom(self, delta):
        """Adjust zoom level via plus/minus buttons."""
        try:
            current_page_index, offset_in_page = self.get_current_page_info()
            
            new_zoom_percent = int(self.zoom * 100) + delta
            new_zoom_percent = max(20, min(300, new_zoom_percent))
            self.zoom_lineedit.setText(str(new_zoom_percent))
            self.zoom = new_zoom_percent / 100.0
            
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

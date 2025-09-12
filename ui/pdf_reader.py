from PyQt5.QtCore import Qt
from PyQt5.QtGui import QImage, QPixmap, QIntValidator, QKeySequence
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QFileDialog, QScrollArea, QLineEdit, QFrame,
    QMessageBox
)
import fitz  # PyMuPDF
from ui.page_label import ClickablePageLabel
from styles import apply_style
import pyperclip

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
        self.zoom = 2.2
        self.base_zoom = 2.2
        self.dark_mode = True
        self.page_spacing = 30
        self.page_height = None
        self.loaded_pages = {}
        self.current_page_index = 0

        # Search state
        self.search_results = []
        self.current_search_index = -1
        self.current_search_term = ""
        
        self.setup_ui()
        self.apply_style()

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
        
        self.open_button = QPushButton("Open PDF", self.top_frame)
        self.open_button.clicked.connect(self.open_pdf)
        self.top_layout.addWidget(self.open_button)
        
        self.toggle_button = QPushButton("Toggle Dark Mode", self.top_frame)
        self.toggle_button.clicked.connect(self.toggle_mode)
        self.top_layout.addWidget(self.toggle_button)
        
        self.top_layout.addStretch() # Pushes zoom controls to the right
        
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
        #         SEARCH BAR
        # -----------------------------
        self.search_frame = QFrame()
        self.search_frame.setObjectName("SearchFrame")
        self.search_layout = QHBoxLayout(self.search_frame)
        self.search_layout.setContentsMargins(5, 5, 5, 5)
        
        self.search_input = QLineEdit(self.search_frame)
        self.search_input.setPlaceholderText("Search document...")
        self.search_input.returnPressed.connect(self._execute_search)
        self.search_layout.addWidget(self.search_input)

        self.prev_button = QPushButton("Previous", self.search_frame)
        self.prev_button.clicked.connect(self._find_prev)
        self.search_layout.addWidget(self.prev_button)

        self.next_button = QPushButton("Next", self.search_frame)
        self.next_button.clicked.connect(self._find_next)
        self.search_layout.addWidget(self.next_button)

        self.search_status_label = QLabel("", self.search_frame)
        self.search_layout.addWidget(self.search_status_label)
        
        self.close_search_button = QPushButton("X", self.search_frame)
        self.close_search_button.setFixedWidth(30)
        self.close_search_button.clicked.connect(self._hide_search_bar)
        self.search_layout.addWidget(self.close_search_button)
        self.search_frame.hide() # Hidden by default
        
        # -----------------------------
        #      PAGE DISPLAY AREA
        # -----------------------------
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
        main_layout.addWidget(self.search_frame) # Add search bar here
        main_layout.addWidget(self.scroll_area)
        container = QWidget()
        container.setLayout(main_layout)
        self.setCentralWidget(container)
        
    def keyPressEvent(self, event):
        """Handle keyboard shortcuts."""
        if event.matches(QKeySequence.Copy):
            self.copy_selected_text()
            event.accept()
        elif event.matches(QKeySequence.Find):
            self._show_search_bar()
            event.accept()
        elif event.key() == Qt.Key_Escape:
            if self.search_frame.isVisible():
                self._hide_search_bar()
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
            pyperclip.copy(selected_text)
            QMessageBox.information(self, "Success", "Selected text copied to clipboard!")
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
            self._clear_search() # Clear previous search results
            self.clear_loaded_pages()
            self.page_height = None
            self.update_visible_pages()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error loading PDF: {e}")
    
    def clear_loaded_pages(self):
        """Remove all loaded page widgets."""
        for label in self.loaded_pages.values():
            label.deleteLater()
        self.loaded_pages.clear()
    
    def render_page(self, page_index):
        try:
            page = self.doc.load_page(page_index)
            mat = fitz.Matrix(self.zoom, self.zoom)
            
            pix = page.get_pixmap(matrix=mat)
            img = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format_RGB888)
            if self.dark_mode:
                img.invertPixels()
            pixmap = QPixmap.fromImage(img)
            
            text_data = page.get_text("dict", sort=True)
            word_data = page.get_text("words", sort=True)

            if self.page_height is None:
                self.page_height = pixmap.height()
                total_height = self.total_pages * (self.page_height + self.page_spacing) - self.page_spacing
                self.page_container.setMinimumHeight(total_height)
                
            return pixmap, text_data, word_data
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error rendering page {page_index+1}: {e}")
            return None, None, None
    
    def update_visible_pages(self):
        if self.doc is None or self.total_pages == 0:
            return

        if self.page_height is None:
            if 0 not in self.loaded_pages:
                self._load_and_display_page(0)

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
        
        for idx in list(self.loaded_pages.keys()):
            if idx < start_index or idx > end_index:
                self.loaded_pages[idx].deleteLater()
                del self.loaded_pages[idx]
        
        for idx in range(start_index, end_index + 1):
            if idx not in self.loaded_pages:
                self._load_and_display_page(idx)

    def _load_and_display_page(self, idx):
        """Loads, configures, and displays a single page widget."""
        pix, text_data, word_data = self.render_page(idx)
        if pix:
            # Get search results for this specific page
            rects_on_page = [r for p, r in self.search_results if p == idx]
            current_idx_on_page = -1
            if self.current_search_index != -1 and self.search_results[self.current_search_index][0] == idx:
                current_rect = self.search_results[self.current_search_index][1]
                if current_rect in rects_on_page:
                    current_idx_on_page = rects_on_page.index(current_rect)

            label = ClickablePageLabel(self.page_container)
            label.set_page_data(
                pix, text_data, word_data, self.zoom, self.dark_mode, 
                search_highlights=rects_on_page, 
                current_highlight_index=current_idx_on_page
            )
            label.setAlignment(Qt.AlignCenter)
            container_width = self.page_container.width()
            x = (container_width - pix.width()) // 2
            y = idx * (self.page_height + self.page_spacing)
            label.setGeometry(x, y, pix.width(), pix.height())
            label.show()
            self.loaded_pages[idx] = label

    def update_current_page_display(self):
        if self.page_height is None: return
        vsb = self.scroll_area.verticalScrollBar()
        scroll_val = vsb.value()
        viewport_height = self.scroll_area.viewport().height()
        H = self.page_height + self.page_spacing
        current_page = round((scroll_val + viewport_height / 2 - self.page_height / 2) / H)
        current_page = max(0, min(self.total_pages - 1, current_page))
        if not self.page_edit.hasFocus():
            self.page_edit.setText(str(current_page + 1))
    
    def on_scroll(self):
        self.update_visible_pages()
        self.update_current_page_display()
    
    def page_number_changed(self):
        if self.page_height is None: return
        try:
            page_num = int(self.page_edit.text())
            if 1 <= page_num <= self.total_pages:
                target_y = (page_num - 1) * (self.page_height + self.page_spacing)
                self.scroll_area.verticalScrollBar().setValue(target_y)
            else:
                self.page_edit.setText(str(self.current_page_index + 1))
        except (ValueError, IndexError):
            self.page_edit.setText(str(self.current_page_index + 1))

    def get_current_page_info(self):
        if self.page_height is None or self.page_height == 0: return 0, 0
        vsb = self.scroll_area.verticalScrollBar()
        scroll_val = vsb.value()
        H = self.page_height + self.page_spacing
        current_page_index = int(scroll_val / H)
        offset_in_page = scroll_val % H
        return current_page_index, offset_in_page
    
    def manual_zoom_changed(self):
        """Update zoom level when the user enters a new value."""
        self._handle_zoom_change(int(self.zoom_lineedit.text()))

    def adjust_zoom(self, delta):
        """Adjust zoom level via plus/minus buttons."""
        current_zoom_percent = int((self.zoom / self.base_zoom) * 100)
        new_zoom_percent = max(20, min(300, current_zoom_percent + delta))
        self.zoom_lineedit.setText(str(new_zoom_percent))
        self._handle_zoom_change(new_zoom_percent)

    def _handle_zoom_change(self, new_zoom_percent):
        try:
            current_page_index, offset_in_page = self.get_current_page_info()
            self.zoom = (new_zoom_percent / 100.0) * self.base_zoom
            
            if self.doc:
                self.clear_loaded_pages()
                self.page_height = None
                self.update_visible_pages()
                
                if self.page_height: # Check if a page was rendered
                    new_scroll_pos = current_page_index * (self.page_height + self.page_spacing) + offset_in_page
                    self.scroll_area.verticalScrollBar().setValue(new_scroll_pos)
                    # If searching, re-jump to keep the highlighted result centered
                    if self.search_results:
                        self._jump_to_current_search_result()
                
        except (ValueError, IndexError):
            current_zoom_percent = int((self.zoom / self.base_zoom) * 100)
            self.zoom_lineedit.setText(str(current_zoom_percent))

    def toggle_mode(self):
        self.dark_mode = not self.dark_mode
        self.apply_style()
        if self.doc:
            current_page_index, offset_in_page = self.get_current_page_info()
            self.clear_loaded_pages()
            self.page_height = None
            self.update_visible_pages()
            if self.page_height:
                new_scroll_pos = current_page_index * (self.page_height + self.page_spacing) + offset_in_page
                self.scroll_area.verticalScrollBar().setValue(new_scroll_pos)

    # --- SEARCH METHODS ---

    def _show_search_bar(self):
        """Makes the search bar visible and focuses it."""
        self.search_frame.show()
        self.search_input.setFocus()
        self.search_input.selectAll()

    def _hide_search_bar(self):
        """Hides the search bar and clears search results."""
        self.search_frame.hide()
        self._clear_search()

    def _execute_search(self):
        """Performs a new search across the entire document."""
        search_term = self.search_input.text()
        if not search_term:
            self._clear_search()
            return

        # If the search term is new, perform a full search
        if search_term != self.current_search_term:
            self.current_search_term = search_term
            self.search_results = []
            for i in range(self.total_pages):
                page = self.doc.load_page(i)
                results_on_page = page.search_for(search_term, quads=False)
                for rect in results_on_page:
                    self.search_results.append((i, rect))
            
            self.current_search_index = -1
            if not self.search_results:
                self.search_status_label.setText("0 results")
                self._update_all_page_highlights()
                return

        self._find_next()

    def _find_next(self):
        """Jumps to the next search result."""
        if not self.search_results: return
        self.current_search_index = (self.current_search_index + 1) % len(self.search_results)
        self._jump_to_current_search_result()

    def _find_prev(self):
        """Jumps to the previous search result."""
        if not self.search_results: return
        self.current_search_index = (self.current_search_index - 1 + len(self.search_results)) % len(self.search_results)
        self._jump_to_current_search_result()

    def _jump_to_current_search_result(self):
        """Scrolls to and highlights the current search result."""
        if self.current_search_index == -1 or self.page_height is None: return

        page_idx, rect = self.search_results[self.current_search_index]
        
        # Center the result in the viewport
        scroll_offset = self.scroll_area.height() / 2 - (rect.height * self.zoom) / 2
        target_y = (page_idx * (self.page_height + self.page_spacing)) + (rect.y0 * self.zoom) - scroll_offset
        
        self.scroll_area.verticalScrollBar().setValue(int(target_y))
        
        self.search_status_label.setText(f"{self.current_search_index + 1} of {len(self.search_results)}")
        self._update_all_page_highlights()

    def _clear_search(self):
        """Resets the search state and removes all highlights."""
        self.search_results = []
        self.current_search_index = -1
        self.current_search_term = ""
        self.search_input.clear()
        self.search_status_label.setText("")
        self._update_all_page_highlights()

    def _update_all_page_highlights(self):
        """Updates search highlights on all currently loaded pages."""
        for idx, label in self.loaded_pages.items():
            rects_on_page = [r for p, r in self.search_results if p == idx]
            current_idx_on_page = -1
            if self.current_search_index != -1:
                current_page, current_rect = self.search_results[self.current_search_index]
                if current_page == idx and current_rect in rects_on_page:
                    current_idx_on_page = rects_on_page.index(current_rect)
            
            label.set_search_highlights(rects_on_page, current_idx_on_page)
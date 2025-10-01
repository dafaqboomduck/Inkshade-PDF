from PyQt5.QtGui import QIntValidator
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QFileDialog, QScrollArea, QLineEdit, QFrame,
    QMessageBox, QSpacerItem, QSizePolicy
)
import pyperclip
import os
from core.pdf_reader import PDFDocumentReader
from core.user_input import UserInputHandler
# from ui.page_label import ClickablePageLabel # Not directly needed here anymore
from styles import apply_style
from ui.pdf_view import PDFViewer # Import the new class

class MainWindow(QMainWindow): # Renamed for clarity
    def __init__(self, file_path=None):
        super().__init__()
        self.setWindowTitle("PDF Reader")
        
        # Core PDF reading utility
        self.pdf_reader = PDFDocumentReader()
        
        # State variables
        self.zoom = 2.2
        self.base_zoom = 2.2
        self.dark_mode = True
        self.page_spacing = 30
        self.page_height = None # Managed by PDFPageManager, but stored here for scroll calcs
        self.loaded_pages = {} # Dictionary of currently loaded page labels: {index: ClickablePageLabel}
        self.current_page_index = 0

        self.input_handler = UserInputHandler(self)
        self.page_manager = None # Will be initialized in setup_ui

        self.setup_ui()
        self.apply_style()

        if file_path:
            self.load_pdf(file_path)

    def setup_ui(self):
        # ... (TOP TOOLBAR SETUP REMAINS THE SAME) ...

        # -----------------------------
        #         TOP TOOLBAR
        # -----------------------------
        self.top_frame = QFrame()
        self.top_frame.setObjectName("TopFrame")
        self.top_layout = QHBoxLayout(self.top_frame)
        self.top_layout.setContentsMargins(15, 10, 15, 10)
        self.top_layout.setSpacing(15)
        
        self.open_button = QPushButton("Open PDF", self.top_frame)
        self.open_button.clicked.connect(self.open_pdf)
        self.top_layout.addWidget(self.open_button)

        self.file_name_label = QLabel("No PDF Loaded", self.top_frame)
        self.file_name_label.setStyleSheet("font-weight: bold; color: #8899AA;")
        self.top_layout.addWidget(self.file_name_label)
        
        self.top_layout.addSpacerItem(QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))

        # Page number controls
        self.page_edit = QLineEdit("1", self.top_frame)
        self.page_edit.setObjectName("page_input")
        self.page_edit.returnPressed.connect(self.page_number_changed)
        self.top_layout.addWidget(self.page_edit)
        
        self.total_page_label = QLabel("/ 0", self.top_frame)
        self.top_layout.addWidget(self.total_page_label)
        
        self.top_layout.addSpacerItem(QSpacerItem(20, 20, QSizePolicy.Fixed, QSizePolicy.Minimum))

        # Zoom controls
        self.minus_button = QPushButton("–", self.top_frame)
        self.minus_button.setObjectName("small_button")
        self.minus_button.clicked.connect(lambda: self.adjust_zoom(-20))
        self.top_layout.addWidget(self.minus_button)
        
        self.zoom_lineedit = QLineEdit("100", self.top_frame)
        self.zoom_lineedit.setObjectName("zoom_input")
        self.zoom_lineedit.setValidator(QIntValidator(20, 300, self))
        self.zoom_lineedit.returnPressed.connect(self.manual_zoom_changed)
        self.top_layout.addWidget(self.zoom_lineedit)
        
        self.plus_button = QPushButton("+", self.top_frame)
        self.plus_button.setObjectName("small_button")
        self.plus_button.clicked.connect(lambda: self.adjust_zoom(20))
        self.top_layout.addWidget(self.plus_button)
        
        self.top_layout.addSpacerItem(QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))

        self.toggle_button = QPushButton("Toggle Dark Mode", self.top_frame)
        self.toggle_button.clicked.connect(self.toggle_mode)
        self.top_layout.addWidget(self.toggle_button)
        
        # -----------------------------
        #         SEARCH BAR
        # -----------------------------
        self.search_frame = QFrame()
        self.search_frame.setObjectName("SearchFrame")
        self.search_layout = QHBoxLayout(self.search_frame)
        self.search_layout.setContentsMargins(15, 10, 15, 10)
        self.search_layout.setSpacing(10)
        
        self.search_input = QLineEdit(self.search_frame)
        self.search_input.setPlaceholderText("Search document...")
        self.search_input.returnPressed.connect(self._execute_search)
        self.search_layout.addWidget(self.search_input)

        self.search_status_label = QLabel("", self.search_frame)
        self.search_layout.addWidget(self.search_status_label)
        
        self.search_layout.addSpacerItem(QSpacerItem(10, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))
        
        self.prev_button = QPushButton("Previous", self.search_frame)
        self.prev_button.clicked.connect(self._find_prev)
        self.search_layout.addWidget(self.prev_button)

        self.next_button = QPushButton("Next", self.search_frame)
        self.next_button.clicked.connect(self._find_next)
        self.search_layout.addWidget(self.next_button)

        self.close_search_button = QPushButton("X", self.search_frame)
        self.close_search_button.setObjectName("small_button")
        self.close_search_button.clicked.connect(self._hide_search_bar)
        self.search_layout.addWidget(self.close_search_button)
        self.search_frame.hide()

        # -----------------------------
        #      PAGE DISPLAY AREA
        # -----------------------------
        self.page_container = QWidget()
        # self.page_container.setMinimumHeight(0) # Moved to PDFPageManager
        # self.page_container.resizeEvent = self.container_resize_event # Moved to PDFPageManager
        
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setWidget(self.page_container)
        self.scroll_area.verticalScrollBar().valueChanged.connect(self.on_scroll)
        
        # INITIALIZE PAGE MANAGER
        self.page_manager = PDFViewer(
            main_window=self, 
            page_container_widget=self.page_container,
            scroll_area_widget=self.scroll_area,
            pdf_reader_core=self.pdf_reader
        )
        
        # -----------------------------
        #         MAIN LAYOUT
        # -----------------------------
        main_layout = QVBoxLayout()
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(self.top_frame)
        main_layout.addWidget(self.search_frame)
        main_layout.addWidget(self.scroll_area)
        container = QWidget()
        container.setLayout(main_layout)
        self.setCentralWidget(container)

    def keyPressEvent(self, event):
        self.input_handler.handle_key_press(event)

    def apply_style(self):
        apply_style(self, self.dark_mode)
    
    def copy_selected_text(self):
        # NOTE: This logic assumes ClickablePageLabel is accessible via loaded_pages
        if self.pdf_reader.doc is None or self.current_page_index not in self.loaded_pages:
            QMessageBox.warning(self, "No Page Loaded", "Please load a PDF document first.")
            return

        current_page_widget = self.loaded_pages[self.current_page_index]
        selected_text = current_page_widget.get_selected_text()
        
        if selected_text:
            pyperclip.copy(selected_text)
            # QMessageBox.information(self, "Success", "Selected text copied to clipboard!")
        else:
            QMessageBox.information(self, "No Selection", "No text has been selected on the current page.")
            
    # REMOVED: container_resize_event - now in PDFPageManager
    
    def open_pdf(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Open PDF", "", "PDF Files (*.pdf)")
        if file_path:
            self.load_pdf(file_path)
    
    def load_pdf(self, file_path):
        success, total_pages = self.pdf_reader.load_pdf(file_path)
        if success:
            self.total_page_label.setText(f"/ {total_pages}")
            self.page_edit.setValidator(QIntValidator(1, total_pages, self))
            self.file_name_label.setText(os.path.basename(file_path))
            
            self.page_manager.clear_all()
            self.current_page_index = 0
            self.update_visible_pages()
    
    # REMOVED: clear_loaded_pages - logic moved to page_manager.clear_all()
    
    def update_visible_pages(self):
        """Delegates the page loading/unloading to the manager."""
        current_page = self.page_manager.get_current_page_index()
        self.current_page_index = current_page
        self.page_manager.update_visible_pages(current_page)

    # REMOVED: _load_and_display_page - now in PDFPageManager

    def update_current_page_display(self):
        """Updates the page number input field."""
        if self.page_height is None: return
        self.current_page_index = self.page_manager.get_current_page_index()
        if not self.page_edit.hasFocus():
            self.page_edit.setText(str(self.current_page_index + 1))
    
    def on_scroll(self):
        self.update_visible_pages()
        self.update_current_page_display()
    
    def page_number_changed(self):
        if self.page_height is None: return
        try:
            page_num = int(self.page_edit.text())
            if 1 <= page_num <= self.pdf_reader.total_pages:
                self.page_manager.jump_to_page(page_num)
            else:
                self.page_edit.setText(str(self.current_page_index + 1))
        except (ValueError, IndexError):
            self.page_edit.setText(str(self.current_page_index + 1))

    def get_current_page_info(self):
        """Delegates scroll position info retrieval to the manager."""
        return self.page_manager.get_scroll_info()
    
    def manual_zoom_changed(self):
        self._handle_zoom_change(int(self.zoom_lineedit.text()))

    def adjust_zoom(self, delta):
        current_zoom_percent = int((self.zoom / self.base_zoom) * 100)
        new_zoom_percent = max(20, min(300, current_zoom_percent + delta))
        self.zoom_lineedit.setText(str(new_zoom_percent))
        self._handle_zoom_change(new_zoom_percent)

    def _handle_zoom_change(self, new_zoom_percent):
        try:
            current_page_index, offset_in_page = self.get_current_page_info()
            
            # 1. Update zoom state and manager
            self.zoom = (new_zoom_percent / 100.0) * self.base_zoom
            self.page_manager.set_zoom(self.zoom)
            
            if self.pdf_reader.doc:
                # 2. Reset and re-render pages with new zoom
                self.page_manager.clear_all()
                self.update_visible_pages() # This will calculate new self.page_height
                
                # 3. Restore scroll position
                if self.page_height:
                    # New scroll position is based on the old index and offset,
                    # but using the new page height.
                    new_scroll_pos = current_page_index * (self.page_height + self.page_spacing) + offset_in_page
                    self.scroll_area.verticalScrollBar().setValue(new_scroll_pos)
                    if self.pdf_reader.search_results:
                        self._jump_to_current_search_result()
                
        except (ValueError, IndexError):
            current_zoom_percent = int((self.zoom / self.base_zoom) * 100)
            self.zoom_lineedit.setText(str(current_zoom_percent))

    def toggle_mode(self):
        self.dark_mode = not self.dark_mode
        self.apply_style()
        self.page_manager.set_dark_mode(self.dark_mode)
        
        if self.pdf_reader.doc:
            current_page_index, offset_in_page = self.get_current_page_info()
            
            self.page_manager.clear_all()
            self.update_visible_pages() # This re-renders and sets new self.page_height
            
            if self.page_height:
                new_scroll_pos = current_page_index * (self.page_height + self.page_spacing) + offset_in_page
                self.scroll_area.verticalScrollBar().setValue(new_scroll_pos)

    # --- SEARCH METHODS ---

    def _show_search_bar(self):
        self.search_frame.show()
        self.search_input.setFocus()
        self.search_input.selectAll()

    def _hide_search_bar(self):
        self.search_frame.hide()
        self._clear_search()

    def _execute_search(self):
        search_term = self.search_input.text()
        num_results = self.pdf_reader.execute_search(search_term)
        
        if num_results > 0:
            self._find_next()
        else:
            self.search_status_label.setText("0 results")
            self.page_manager.update_page_highlights() # Use manager for update

    def _find_next(self):
        self.pdf_reader.next_search_result()
        self._jump_to_current_search_result()

    def _find_prev(self):
        self.pdf_reader.prev_search_result()
        self._jump_to_current_search_result()

    def _jump_to_current_search_result(self):
        page_idx, rect = self.pdf_reader.get_search_result_info()
        
        # Delegate the scrolling and highlighting to the manager
        self.page_manager.jump_to_search_result(page_idx, rect)
        
        if page_idx is not None:
            self.search_status_label.setText(f"{self.pdf_reader.current_search_index + 1} of {len(self.pdf_reader.search_results)}")

    def _clear_search(self):
        self.pdf_reader._clear_search()
        self.search_input.clear()
        self.search_status_label.setText("")
        self.page_manager.update_page_highlights() # Use manager for update

    # REMOVED: _update_all_page_highlights - logic moved to page_manager.update_page_highlights()
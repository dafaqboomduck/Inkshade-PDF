from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIntValidator, QKeySequence
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QFileDialog, QScrollArea, QLineEdit, QFrame,
    QMessageBox, QSpacerItem, QSizePolicy
)
import pyperclip
import os
from core.pdf_reader import PDFDocumentReader
from ui.page_label import ClickablePageLabel
from styles import apply_style

class PDFReader(QMainWindow):
    def __init__(self, file_path=None):
        super().__init__()
        self.setWindowTitle("PDF Reader")
        
        self.pdf_reader = PDFDocumentReader()
        self.zoom = 2.2
        self.base_zoom = 2.2
        self.dark_mode = True
        self.page_spacing = 30
        self.page_height = None
        self.loaded_pages = {}
        self.current_page_index = 0

        self.setup_ui()
        self.apply_style()

        if file_path:
            self.load_pdf(file_path)

    def setup_ui(self):
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
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(self.top_frame)
        main_layout.addWidget(self.search_frame)
        main_layout.addWidget(self.scroll_area)
        container = QWidget()
        container.setLayout(main_layout)
        self.setCentralWidget(container)

    def keyPressEvent(self, event):
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
        apply_style(self, self.dark_mode)
    
    def copy_selected_text(self):
        if self.pdf_reader.doc is None or self.current_page_index not in self.loaded_pages:
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
        success, total_pages = self.pdf_reader.load_pdf(file_path)
        if success:
            self.total_page_label.setText(f"/ {total_pages}")
            self.page_edit.setValidator(QIntValidator(1, total_pages, self))
            self.file_name_label.setText(os.path.basename(file_path))
            self.clear_loaded_pages()
            self.page_height = None
            self.update_visible_pages()
    
    def clear_loaded_pages(self):
        for label in self.loaded_pages.values():
            label.deleteLater()
        self.loaded_pages.clear()
    
    def update_visible_pages(self):
        if self.pdf_reader.doc is None or self.pdf_reader.total_pages == 0:
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
        current_page = max(0, min(self.pdf_reader.total_pages - 1, current_page))
        self.current_page_index = current_page
        
        start_index = max(0, current_page - 7)
        end_index = min(self.pdf_reader.total_pages - 1, current_page + 7)
        
        for idx in list(self.loaded_pages.keys()):
            if idx < start_index or idx > end_index:
                self.loaded_pages[idx].deleteLater()
                del self.loaded_pages[idx]
        
        for idx in range(start_index, end_index + 1):
            if idx not in self.loaded_pages:
                self._load_and_display_page(idx)

    def _load_and_display_page(self, idx):
        pix, text_data, word_data = self.pdf_reader.render_page(idx, self.zoom, self.dark_mode)
        if pix:
            search_results = self.pdf_reader.get_all_search_results()
            rects_on_page = [r for p, r in search_results if p == idx]
            current_idx_on_page = -1
            if self.pdf_reader.current_search_index != -1 and search_results[self.pdf_reader.current_search_index][0] == idx:
                current_rect = search_results[self.pdf_reader.current_search_index][1]
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
                total_height = self.pdf_reader.total_pages * (self.page_height + self.page_spacing) - self.page_spacing
                self.page_container.setMinimumHeight(total_height)
            
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
        current_page = max(0, min(self.pdf_reader.total_pages - 1, current_page))
        self.current_page_index = current_page
        if not self.page_edit.hasFocus():
            self.page_edit.setText(str(current_page + 1))
    
    def on_scroll(self):
        self.update_visible_pages()
        self.update_current_page_display()
    
    def page_number_changed(self):
        if self.page_height is None: return
        try:
            page_num = int(self.page_edit.text())
            if 1 <= page_num <= self.pdf_reader.total_pages:
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
        self._handle_zoom_change(int(self.zoom_lineedit.text()))

    def adjust_zoom(self, delta):
        current_zoom_percent = int((self.zoom / self.base_zoom) * 100)
        new_zoom_percent = max(20, min(300, current_zoom_percent + delta))
        self.zoom_lineedit.setText(str(new_zoom_percent))
        self._handle_zoom_change(new_zoom_percent)

    def _handle_zoom_change(self, new_zoom_percent):
        try:
            current_page_index, offset_in_page = self.get_current_page_info()
            self.zoom = (new_zoom_percent / 100.0) * self.base_zoom
            
            if self.pdf_reader.doc:
                self.clear_loaded_pages()
                self.page_height = None
                self.update_visible_pages()
                
                if self.page_height:
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
        if self.pdf_reader.doc:
            current_page_index, offset_in_page = self.get_current_page_info()
            self.clear_loaded_pages()
            self.page_height = None
            self.update_visible_pages()
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
            self._update_all_page_highlights()

    def _find_next(self):
        self.pdf_reader.next_search_result()
        self._jump_to_current_search_result()

    def _find_prev(self):
        self.pdf_reader.prev_search_result()
        self._jump_to_current_search_result()

    def _jump_to_current_search_result(self):
        page_idx, rect = self.pdf_reader.get_search_result_info()
        if page_idx is None or self.page_height is None:
            return

        scroll_offset = self.scroll_area.height() / 2 - (rect.height * self.zoom) / 2
        target_y = (page_idx * (self.page_height + self.page_spacing)) + (rect.y0 * self.zoom) - scroll_offset
        
        self.scroll_area.verticalScrollBar().setValue(int(target_y))
        
        self.search_status_label.setText(f"{self.pdf_reader.current_search_index + 1} of {len(self.pdf_reader.search_results)}")
        self._update_all_page_highlights()

    def _clear_search(self):
        self.pdf_reader._clear_search()
        self.search_input.clear()
        self.search_status_label.setText("")
        self._update_all_page_highlights()

    def _update_all_page_highlights(self):
        for idx, label in self.loaded_pages.items():
            search_results = self.pdf_reader.get_all_search_results()
            rects_on_page = [r for p, r in search_results if p == idx]
            current_idx_on_page = -1
            if self.pdf_reader.current_search_index != -1:
                current_page, current_rect = search_results[self.pdf_reader.current_search_index]
                if current_page == idx and current_rect in rects_on_page:
                    current_idx_on_page = rects_on_page.index(current_rect)
            
            label.set_search_highlights(rects_on_page, current_idx_on_page)
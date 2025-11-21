from PyQt5.QtCore import Qt, QTimer, QSize
from PyQt5.QtGui import QIntValidator, QIcon, QPixmap, QPainter, QColor
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QFileDialog, QScrollArea, QLineEdit, QFrame,
    QMessageBox, QSpacerItem, QSizePolicy, QApplication, 
    QDockWidget, QTreeWidget, QTreeWidgetItem, QToolButton,
    QProgressDialog
)
import pyperclip
import os
import tempfile
import shutil
from core.document.pdf_reader import PDFDocumentReader
from controllers.input_handler import UserInputHandler
from core.annotations import AnnotationManager
from core.document.pdf_exporter import PDFExporter
from core.export.export_worker import ExportWorker
from styles.theme_manager import apply_style
from ui.widgets.pdf_viewer import PDFViewer
from ui.widgets.toc_widget import TOCWidget
from ui.toolbars.annotation_toolbar import AnnotationToolbar
from ui.toolbars.drawing_toolbar import DrawingToolbar
from ui.toolbars.search_bar import SearchBar
from utils.resource_loader import get_resource_path

class MainWindow(QMainWindow):
    def __init__(self, file_path=None):
        super().__init__()

        icon_path = get_resource_path("resources/icons/inkshade.ico")
        
        self.setWindowIcon(QIcon(icon_path))
        self.setWindowTitle("Inkshade PDF")
        
        self.pdf_reader = PDFDocumentReader()
        self.annotation_manager = AnnotationManager()
        
        self.zoom = 2.2
        self.base_zoom = 2.2
        self.dark_mode = True
        self.page_spacing = 30
        self.page_height = None
        self.loaded_pages = {}
        self.current_page_index = 0

        self.input_handler = UserInputHandler(self)
        self.page_manager = None

        self.toc_widget = TOCWidget()

        self.setup_ui()
        self.apply_style()

        if file_path:
            self.load_pdf(file_path)

    def create_icon_button(self, icon_path, tooltip, parent=None):
        """Helper to create icon-style buttons with image icons."""
        btn = QToolButton(parent)
        
        # Load icon if path provided, otherwise use text fallback
        if icon_path and os.path.exists(get_resource_path(icon_path)):
            # Load the original pixmap
            pixmap = QPixmap(get_resource_path(icon_path))
            
            # Create a new pixmap with the desired color
            colored_pixmap = QPixmap(pixmap.size())
            colored_pixmap.fill(Qt.transparent)
            
            # Paint the icon in the desired color
            painter = QPainter(colored_pixmap)
            painter.setCompositionMode(QPainter.CompositionMode_Source)
            painter.drawPixmap(0, 0, pixmap)
            painter.setCompositionMode(QPainter.CompositionMode_SourceIn)
            
            # Use different colors based on dark mode
            if self.dark_mode:
                painter.fillRect(colored_pixmap.rect(), QColor(181, 181, 197))  # Light gray for dark mode
            else:
                painter.fillRect(colored_pixmap.rect(), QColor(122, 137, 156))  # Darker gray for light mode
            painter.end()
            
            icon = QIcon(colored_pixmap)
            btn.setIcon(icon)
            btn.setIconSize(QSize(20, 20))
        
        btn.setToolTip(tooltip)
        btn.setFixedSize(36, 36)
        # btn.setStyleSheet("""
        #     QToolButton {
        #         background-color: transparent;
        #         border: none;
        #         border-radius: 4px;
        #         color: #B5B5C5;
        #         padding: 0px;
        #     }
        #     QToolButton:hover {
        #         background-color: #3e3e3e;
        #     }
        #     QToolButton:pressed {
        #         background-color: #2e2e2e;
        #     }
        # """)
        return btn
    
    def closeEvent(self, event):
        """Handle window close event - check for unsaved changes."""
        if self.annotation_manager.has_unsaved_changes:
            reply = QMessageBox.question(
                self,
                "Unsaved Changes",
                "You have unsaved annotations. Do you want to save them to the PDF?",
                QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
                QMessageBox.Save
            )
            
            if reply == QMessageBox.Save:
                # Trigger OS save dialog
                if self.save_annotations_to_pdf():
                    # Clean up JSON file after successful save
                    self.annotation_manager.delete_json_file()
                    event.accept()
                else:
                    # User cancelled the save dialog
                    event.ignore()
            elif reply == QMessageBox.Discard:
                # Discard changes and delete JSON file
                self.annotation_manager.delete_json_file()
                event.accept()
            else:  # Cancel
                event.ignore()
        else:
            event.accept()

    def save_annotations_to_pdf(self):
        """Save annotations to PDF file using background thread."""
        if not self.pdf_reader.doc or not self.annotation_manager.pdf_path:
            QMessageBox.warning(self, "No PDF", "No PDF document is currently loaded.")
            return False
        
        if self.annotation_manager.get_annotation_count() == 0:
            QMessageBox.information(self, "No Annotations", "There are no annotations to save.")
            return False
        
        # Let user choose where to save (default to current file location)
        default_name = os.path.basename(self.annotation_manager.pdf_path)
        default_dir = os.path.dirname(self.annotation_manager.pdf_path)
        default_path = os.path.join(default_dir, default_name)
        
        output_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Annotated PDF",
            default_path,
            "PDF Files (*.pdf)"
        )
        
        if not output_path:
            return False
        
        # Store info before closing
        temp_annotations = self.annotation_manager.annotations.copy()
        original_pdf_path = self.annotation_manager.pdf_path
        saving_to_same_file = os.path.abspath(output_path) == os.path.abspath(original_pdf_path)
        
        # Always close the document before saving
        self.pdf_reader.close_document()
        
        # Create progress dialog
        progress = QProgressDialog("Preparing to export annotations...", None, 0, 100, self)
        progress.setWindowTitle("Saving PDF")
        progress.setWindowModality(Qt.WindowModal)
        progress.setMinimumDuration(0)
        progress.setCancelButton(None)  # No cancel button - operation must complete
        progress.setAutoClose(False)
        progress.setAutoReset(False)
        progress.show()
        
        # Create and configure worker thread
        self.export_worker = ExportWorker(
            original_pdf_path,
            output_path,
            temp_annotations,
            use_temp_file=saving_to_same_file
        )
        
        # Connect signals
        def on_progress(message):
            progress.setLabelText(message)
        
        def on_page_progress(current, total):
            if total > 0:
                percent = int((current / total) * 100)
                progress.setValue(percent)
                progress.setLabelText(f"Processing annotations: {current}/{total} pages")
        
        def on_finished(success, message):
            progress.close()
            
            if success:
                # Delete the JSON file since annotations are now in the PDF
                self.annotation_manager.delete_json_file()
                self.annotation_manager.mark_saved()
                
                QMessageBox.information(self, "Success", message)
                
                # Reload the PDF
                self.load_pdf(output_path)
            else:
                QMessageBox.critical(self, "Save Failed", message)
                
                # Reopen the original file if save failed
                self.load_pdf(original_pdf_path)
            
            # Clean up worker
            self.export_worker.deleteLater()
            self.export_worker = None
        
        self.export_worker.progress.connect(on_progress)
        self.export_worker.page_progress.connect(on_page_progress)
        self.export_worker.finished.connect(on_finished)
        
        # Start the export in background
        self.export_worker.start()
        
        return True
    
    def setup_ui(self):
        # TOP TOOLBAR
        self.top_frame = QFrame()
        self.top_frame.setObjectName("TopFrame")
        self.top_layout = QHBoxLayout(self.top_frame)
        self.top_layout.setContentsMargins(10, 8, 10, 8)
        self.top_layout.setSpacing(8)
        
        # Store button references for later color updates
        self.icon_buttons = []
        
        # Open PDF Button
        self.open_button = self.create_icon_button("resources/icons/open-icon.png", "Open PDF (Ctrl+O)", self.top_frame)
        self.open_button.clicked.connect(self.open_pdf)
        self.top_layout.addWidget(self.open_button)
        self.icon_buttons.append((self.open_button, "resources/icons/open-icon.png"))

        # Close PDF Button
        self.close_button = self.create_icon_button("resources/icons/close-icon.png", "Close PDF (Ctrl+W)", self.top_frame)
        self.close_button.clicked.connect(self.close_pdf)
        self.top_layout.addWidget(self.close_button)
        self.icon_buttons.append((self.close_button, "resources/icons/close-icon.png"))

        # Separator
        separator1 = QFrame()
        separator1.setFrameShape(QFrame.VLine)
        separator1.setFrameShadow(QFrame.Sunken)
        separator1.setStyleSheet("background-color: #555555; max-width: 1px;")
        self.top_layout.addWidget(separator1)

        # TOC Button
        self.toc_button = self.create_icon_button("resources/icons/toc-icon.png", "Table of Contents", self.top_frame)
        self.toc_button.clicked.connect(self.toggle_toc_view)
        self.top_layout.addWidget(self.toc_button)
        self.icon_buttons.append((self.toc_button, "resources/icons/toc-icon.png"))

        # Search Button
        self.search_button = self.create_icon_button("resources/icons/search-icon.png", "Search (Ctrl+F)", self.top_frame)
        self.search_button.clicked.connect(self.show_search_bar)
        self.top_layout.addWidget(self.search_button)
        self.icon_buttons.append((self.search_button, "resources/icons/search-icon.png"))

        self.top_layout.addSpacerItem(QSpacerItem(15, 20, QSizePolicy.Fixed, QSizePolicy.Minimum))

        # File name label
        self.file_name_label = QLabel("No PDF Loaded", self.top_frame)
        self.file_name_label.setStyleSheet("font-weight: bold; color: #8899AA;")
        self.top_layout.addWidget(self.file_name_label)
        
        self.top_layout.addSpacerItem(QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))

        # Page controls
        self.page_edit = QLineEdit("1", self.top_frame)
        self.page_edit.setObjectName("page_input")
        self.page_edit.setFixedWidth(50)
        self.page_edit.setAlignment(Qt.AlignCenter)
        self.page_edit.returnPressed.connect(self.page_number_changed)
        self.top_layout.addWidget(self.page_edit)
        
        self.total_page_label = QLabel("/ 0", self.top_frame)
        self.top_layout.addWidget(self.total_page_label)
        
        self.top_layout.addSpacerItem(QSpacerItem(15, 20, QSizePolicy.Fixed, QSizePolicy.Minimum))

        # Separator
        separator2 = QFrame()
        separator2.setFrameShape(QFrame.VLine)
        separator2.setFrameShadow(QFrame.Sunken)
        separator2.setStyleSheet("background-color: #555555; max-width: 1px;")
        self.top_layout.addWidget(separator2)

        self.top_layout.addSpacerItem(QSpacerItem(15, 20, QSizePolicy.Fixed, QSizePolicy.Minimum))

        # Zoom controls
        self.zoom_out_button = self.create_icon_button("resources/icons/zoom-out-icon.png", "Zoom Out", self.top_frame)
        self.zoom_out_button.clicked.connect(lambda: self.adjust_zoom(-20))
        self.top_layout.addWidget(self.zoom_out_button)
        self.icon_buttons.append((self.zoom_out_button, "resources/icons/zoom-out-icon.png"))
        
        self.zoom_lineedit = QLineEdit("100", self.top_frame)
        self.zoom_lineedit.setObjectName("zoom_input")
        self.zoom_lineedit.setFixedWidth(50)
        self.zoom_lineedit.setAlignment(Qt.AlignCenter)
        self.zoom_lineedit.setValidator(QIntValidator(20, 300, self))
        self.zoom_lineedit.returnPressed.connect(self.manual_zoom_changed)
        self.top_layout.addWidget(self.zoom_lineedit)
        
        self.zoom_in_button = self.create_icon_button("resources/icons/zoom-in-icon.png", "Zoom In", self.top_frame)
        self.zoom_in_button.clicked.connect(lambda: self.adjust_zoom(20))
        self.top_layout.addWidget(self.zoom_in_button)
        self.icon_buttons.append((self.zoom_in_button, "resources/icons/zoom-in-icon.png"))
        
        self.top_layout.addSpacerItem(QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))

        # Separator
        separator3 = QFrame()
        separator3.setFrameShape(QFrame.VLine)
        separator3.setFrameShadow(QFrame.Sunken)
        separator3.setStyleSheet("background-color: #555555; max-width: 1px;")
        self.top_layout.addWidget(separator3)

        self.top_layout.addSpacerItem(QSpacerItem(15, 20, QSizePolicy.Fixed, QSizePolicy.Minimum))

        # Annotation button
        self.annotate_button = self.create_icon_button("resources/icons/annotate-icon.png", "Annotate Selection", self.top_frame)
        self.annotate_button.clicked.connect(self.show_annotation_toolbar)
        self.top_layout.addWidget(self.annotate_button)
        self.icon_buttons.append((self.annotate_button, "resources/icons/annotate-icon.png"))

        # Draw button
        self.draw_button = self.create_icon_button("resources/icons/draw-icon.png", "Draw", self.top_frame)
        self.draw_button.clicked.connect(self.show_drawing_toolbar)
        self.top_layout.addWidget(self.draw_button)
        self.icon_buttons.append((self.draw_button, "resources/icons/draw-icon.png"))

        # Save button
        self.save_button = self.create_icon_button("resources/icons/save-icon.png", "Save PDF (Ctrl+S)", self.top_frame)
        self.save_button.clicked.connect(self.save_annotations_to_pdf)
        self.top_layout.addWidget(self.save_button)
        self.icon_buttons.append((self.save_button, "resources/icons/save-icon.png"))

        # Dark mode toggle
        self.toggle_button = self.create_icon_button("resources/icons/dark-mode-icon.png", "Toggle Dark Mode", self.top_frame)
        self.toggle_button.clicked.connect(self.toggle_mode)
        self.top_layout.addWidget(self.toggle_button)
        
        # PAGE DISPLAY AREA
        self.page_container = QWidget()
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setWidget(self.page_container)
        self.scroll_area.verticalScrollBar().valueChanged.connect(self.on_scroll)
        
        self.page_manager = PDFViewer(
            main_window=self, 
            page_container_widget=self.page_container,
            scroll_area_widget=self.scroll_area,
            pdf_reader_core=self.pdf_reader,
            annotation_manager=self.annotation_manager
        )
        
        # TOC WIDGET (not a dock, just a regular widget)
        self.toc_widget.toc_link_clicked.connect(self._handle_toc_click)
        self.toc_widget.hide()  # Start hidden

        # MAIN LAYOUT - Create horizontal layout for TOC and content area
        content_layout = QHBoxLayout()
        content_layout.setSpacing(0)
        content_layout.setContentsMargins(0, 0, 0, 0)
        
        # Add TOC on the left
        content_layout.addWidget(self.toc_widget)
        
        # Add scroll area on the right
        content_layout.addWidget(self.scroll_area)
        
        # Content widget to hold the horizontal layout
        content_widget = QWidget()
        content_widget.setLayout(content_layout)
        
        # Main vertical layout
        main_layout = QVBoxLayout()
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(self.top_frame)
        main_layout.addWidget(content_widget)
        
        container = QWidget()
        container.setLayout(main_layout)
        self.setCentralWidget(container)

        # FLOATING TOOLBARS - Parent them to self (QMainWindow), not any layout
        # This ensures they float above everything and maintain their full size
        
        # SEARCH BAR (floating)
        self.search_bar = SearchBar(self)
        self.search_bar.search_requested.connect(self._execute_search)
        self.search_bar.next_result_requested.connect(self._find_next)
        self.search_bar.prev_result_requested.connect(self._find_prev)
        self.search_bar.close_requested.connect(self._clear_search)
        self.search_bar.raise_()

        # ANNOTATION TOOLBAR (floating)
        self.annotation_toolbar = AnnotationToolbar(self)
        self.annotation_toolbar.annotation_requested.connect(self._create_annotation_from_selection)
        self.annotation_toolbar.raise_()

        # DRAWING TOOLBAR (floating)
        self.drawing_toolbar = DrawingToolbar(self)
        self.drawing_toolbar.drawing_mode_changed.connect(self._on_drawing_mode_changed)
        self.drawing_toolbar.tool_changed.connect(self._on_drawing_tool_changed)
        self.drawing_toolbar.raise_()
        
        # Position toolbars after they're created
        QTimer.singleShot(0, self._update_toolbar_positions)
    
    def resizeEvent(self, event):
        """Handle window resize to reposition floating toolbars."""
        super().resizeEvent(event)
        self._update_toolbar_positions()

    def _update_toolbar_positions(self):
        """Update positions of all floating toolbars."""
        # Position from the right edge of the window
        window_width = self.width()
        x = window_width - 18 - 300  # 18px margin, 300px toolbar width
        y = self.top_frame.height() + 20  # Below top frame + 20px margin
        
        if hasattr(self, 'search_bar'):
            self.search_bar.move(x, y)
        
        if hasattr(self, 'annotation_toolbar'):
            self.annotation_toolbar.move(x, y)
        
        if hasattr(self, 'drawing_toolbar'):
            self.drawing_toolbar.move(x, y)

    def _handle_toc_click(self, page_num, y_pos):
        """Handle TOC item clicks with precise positioning."""
        self.page_manager.jump_to_page(page_num, y_pos)

    def keyPressEvent(self, event):
        # Handle undo/redo shortcuts
        if event.modifiers() & Qt.ControlModifier:
            if event.key() == Qt.Key_Z:
                if event.modifiers() & Qt.ShiftModifier:
                    # Ctrl+Shift+Z for redo
                    self.redo_annotation()
                else:
                    # Ctrl+Z for undo
                    self.undo_annotation()
                event.accept()
                return
            elif event.key() == Qt.Key_Y:
                # Ctrl+Y for redo (alternative)
                self.redo_annotation()
                event.accept()
                return
        
        self.input_handler.handle_key_press(event)

    def apply_style(self):
        apply_style(self, self.dark_mode)
        # Update icon colors when style changes
        if hasattr(self, 'icon_buttons'):
            self.update_icon_colors()
        
        # Update toolbar styles
        if hasattr(self, 'search_bar'):
            apply_style(self.search_bar, self.dark_mode)
        if hasattr(self, 'annotation_toolbar'):
            apply_style(self.annotation_toolbar, self.dark_mode)
        if hasattr(self, 'drawing_toolbar'):
            apply_style(self.drawing_toolbar, self.dark_mode)
    
    def update_icon_colors(self):
        """Update all icon colors based on current dark mode setting."""
        for btn, icon_path in self.icon_buttons:
            if os.path.exists(get_resource_path(icon_path)):
                # Load the original pixmap
                pixmap = QPixmap(get_resource_path(icon_path))
                
                # Create a new pixmap with the desired color
                colored_pixmap = QPixmap(pixmap.size())
                colored_pixmap.fill(Qt.transparent)
                
                # Paint the icon in the desired color
                painter = QPainter(colored_pixmap)
                painter.setCompositionMode(QPainter.CompositionMode_Source)
                painter.drawPixmap(0, 0, pixmap)
                painter.setCompositionMode(QPainter.CompositionMode_SourceIn)
                
                # Use different colors based on dark mode
                if self.dark_mode:
                    painter.fillRect(colored_pixmap.rect(), QColor(181, 181, 197))  # Light gray for dark mode
                else:
                    painter.fillRect(colored_pixmap.rect(), QColor(122, 137, 156))  # Darker gray for light mode
                painter.end()
                
                icon = QIcon(colored_pixmap)
                btn.setIcon(icon)
    
    def copy_selected_text(self):
        if self.pdf_reader.doc is None or self.current_page_index not in self.loaded_pages:
            QMessageBox.warning(self, "No Page Loaded", "Please load a PDF document first.")
            return

        current_page_widget = self.loaded_pages[self.current_page_index]
        selected_text = current_page_widget.get_selected_text()
        
        if selected_text:
            pyperclip.copy(selected_text)
        else:
            QMessageBox.information(self, "No Selection", "No text has been selected on the current page.")
    
    def open_pdf(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Open PDF", "", "PDF Files (*.pdf)")
        if file_path:
            self.load_pdf(file_path)
            self._update_undo_redo_buttons()

    # Update the close_pdf method to handle unsaved changes:

    def close_pdf(self):
        """Closes the currently loaded PDF and resets the application state."""
        if self.pdf_reader.doc is None:
            return
        
        # Check for unsaved changes
        if self.annotation_manager.has_unsaved_changes:
            reply = QMessageBox.question(
                self,
                "Unsaved Changes",
                "You have unsaved annotations. Do you want to save them before closing?",
                QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
                QMessageBox.Save
            )
            
            if reply == QMessageBox.Save:
                if not self.save_annotations_to_pdf():
                    return  # User cancelled save
                # JSON already deleted in save_annotations_to_pdf if successful
            elif reply == QMessageBox.Discard:
                self.annotation_manager.delete_json_file()
            else:  # Cancel
                return
        
        self.pdf_reader.close_document()
        self.page_manager.clear_all()
        self.annotation_manager.clear_all()
        self.toc_widget.clear_toc()
        self.toc_widget.hide()
        self.toc_button.setVisible(False)
        self._clear_search()
        self._hide_search_bar()
        self._hide_annotation_toolbar()
        self._hide_drawing_toolbar()
        
        self.file_name_label.setText("No PDF Loaded")
        self.total_page_label.setText("/ 0")
        self.page_edit.setText("1")
        self.page_edit.setValidator(QIntValidator(1, 1, self))
        
        self.current_page_index = 0
        self.page_height = None
        self.loaded_pages.clear()
        self.scroll_area.verticalScrollBar().setValue(0)
        self._update_undo_redo_buttons()

    
    def toggle_toc_view(self):
        """Shows or hides the TOC widget."""
        if self.toc_widget.isVisible():
            self.toc_widget.hide()
        else:
            self.toc_widget.show()
            self.load_toc_data()
        
        # Toolbars will automatically reposition on next resize event

    def load_toc_data(self):
        """Gets TOC data and loads it into the TOC widget."""
        toc_data = self.pdf_reader.get_toc()
        self.toc_widget.load_toc(toc_data)
        has_toc = bool(toc_data)
        self.toc_button.setVisible(has_toc)
        if not has_toc:
            self.toc_widget.hide()
    
    def load_pdf(self, file_path):
        success, total_pages = self.pdf_reader.load_pdf(file_path)
        if success:
            self.total_page_label.setText(f"/ {total_pages}")
            self.page_edit.setValidator(QIntValidator(1, total_pages, self))
            self.file_name_label.setText(os.path.basename(file_path))
            
            # Clear old annotations first
            self.annotation_manager.clear_all()
            
            # Set PDF path in annotation manager
            self.annotation_manager.set_pdf_path(file_path)
            
            # Try to auto-load existing annotations from JSON
            if self.annotation_manager.auto_load_annotations():
                num_annotations = self.annotation_manager.get_annotation_count()
                QMessageBox.information(
                    self,
                    "Annotations Loaded",
                    f"Loaded {num_annotations} existing annotation(s) from previous session."
                )
            
            self.load_toc_data()
            self.page_manager.clear_all()
            self.scroll_area.verticalScrollBar().setValue(0)
            self.current_page_index = 0            
            self.update_visible_pages()
    
    def update_visible_pages(self, desired_page=None):
        if desired_page is not None:
            current_page = int(desired_page)
        elif self.page_height is None:
            current_page = self.current_page_index 
        else:
            current_page = self.page_manager.get_current_page_index()
        self.current_page_index = current_page
        self.page_manager.update_visible_pages(current_page)

    def update_current_page_display(self):
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
        return self.page_manager.get_scroll_info()
    
    def manual_zoom_changed(self):
        self._handle_zoom_change(int(self.zoom_lineedit.text()))

    def adjust_zoom(self, delta):
        current_zoom_percent = int((self.zoom / self.base_zoom) * 100)
        new_zoom_percent = max(20, min(300, current_zoom_percent + delta))
        self.zoom_lineedit.setText(str(new_zoom_percent))
        self._handle_zoom_change(new_zoom_percent)

    def _restore_scroll_position(self, current_page_index, offset_in_page):
        if self.page_height:
            target_y = (current_page_index * (self.page_height + self.page_spacing)) + offset_in_page
            self.scroll_area.verticalScrollBar().setValue(int(target_y))
            if self.pdf_reader.search_results:
                self._jump_to_current_search_result()

    def _handle_zoom_change(self, new_zoom_percent):
        try:
            current_page_index, offset_in_page = self.get_current_page_info()
            self.zoom = (new_zoom_percent / 100.0) * self.base_zoom
            self.page_manager.set_zoom(self.zoom)
            
            if self.pdf_reader.doc:
                self.page_manager.clear_all()
                self.update_visible_pages()
                QApplication.processEvents()
                self.page_container.updateGeometry()
                self.scroll_area.updateGeometry()
                QApplication.processEvents()
                QTimer.singleShot(10, lambda: self._restore_scroll_position(current_page_index, offset_in_page))
        except (ValueError, IndexError):
            current_zoom_percent = int((self.zoom / self.base_zoom) * 100)
            self.zoom_lineedit.setText(str(current_zoom_percent))

    def toggle_mode(self):
        self.dark_mode = not self.dark_mode
        
        # Update icon based on mode with proper coloring
        if self.dark_mode:
            icon_path = "resources/icons/dark-mode-icon.png"
            self.toggle_button.setToolTip("Switch to Light Mode")
        else:
            icon_path = "resources/icons/light-mode-icon.png"
            self.toggle_button.setToolTip("Switch to Dark Mode")
        
        # Apply the colored icon using the same method as other buttons
        if os.path.exists(get_resource_path(icon_path)):
            # Load the original pixmap
            pixmap = QPixmap(get_resource_path(icon_path))
            
            # Create a new pixmap with the desired color
            colored_pixmap = QPixmap(pixmap.size())
            colored_pixmap.fill(Qt.transparent)
            
            # Paint the icon in the desired color
            painter = QPainter(colored_pixmap)
            painter.setCompositionMode(QPainter.CompositionMode_Source)
            painter.drawPixmap(0, 0, pixmap)
            painter.setCompositionMode(QPainter.CompositionMode_SourceIn)
            
            # Use different colors based on dark mode
            if self.dark_mode:
                painter.fillRect(colored_pixmap.rect(), QColor(181, 181, 197))  # Light gray for dark mode
            else:
                painter.fillRect(colored_pixmap.rect(), QColor(122, 137, 156))  # Darker gray for light mode
            painter.end()
            
            icon = QIcon(colored_pixmap)
            self.toggle_button.setIcon(icon)
        
        self.apply_style()
        self.page_manager.set_dark_mode(self.dark_mode)

        if self.pdf_reader.doc:
            current_page_index, offset_in_page = self.get_current_page_info()
            self.page_manager.clear_all()
            self.update_visible_pages(desired_page=current_page_index)

            def _restore():
                self._restore_scroll_position(current_page_index, offset_in_page)
                lbl = self.loaded_pages.get(self.current_page_index)
                if lbl:
                    lbl.repaint()
                self.page_container.repaint()
                self.scroll_area.viewport().repaint()
            QTimer.singleShot(0, _restore)

    # SEARCH METHODS
    def show_search_bar(self):
        if self.search_bar.isVisible():
            self.search_bar.hide()
        else:
            self.annotation_toolbar.hide()
            self.drawing_toolbar.hide()
            self.search_bar.show_bar()
            self.search_bar.raise_()

    def _hide_search_bar(self):
        self.search_bar.hide()
        self._clear_search()

    def _execute_search(self, search_term):
        if not search_term:
            self.search_bar.set_status("0 results")
            self.page_manager.update_page_highlights()
            return
            
        num_results = self.pdf_reader.execute_search(search_term)
        
        if num_results > 0:
            self._find_next()
        else:
            self.search_bar.set_status("0 results")
            self.page_manager.update_page_highlights()

    def _find_next(self):
        self.pdf_reader.next_search_result()
        self._jump_to_current_search_result()

    def _find_prev(self):
        self.pdf_reader.prev_search_result()
        self._jump_to_current_search_result()

    def _jump_to_current_search_result(self):
        page_idx, rect = self.pdf_reader.get_search_result_info()
        self.page_manager.jump_to_search_result(page_idx, rect)
        if page_idx is not None:
            self.search_bar.set_status(f"{self.pdf_reader.current_search_index + 1} of {len(self.pdf_reader.search_results)}")

    def _clear_search(self):
        self.pdf_reader._clear_search()
        self.search_bar.clear_search()
        self.page_manager.update_page_highlights()

    def _create_annotation_from_selection(self, annotation_type, color):
        if self.pdf_reader.doc is None or self.current_page_index not in self.loaded_pages:
            return
        
        current_page_widget = self.loaded_pages[self.current_page_index]
        selected_words = current_page_widget.selected_words
                
        if not selected_words:
            QMessageBox.information(self, "No Selection", "Please select text before creating an annotation.")
            return
        
        quads = self._words_to_quads(selected_words)
                
        if quads:
            from core.annotations import Annotation
            annotation = Annotation(
                page_index=self.current_page_index,
                annotation_type=annotation_type,
                color=color,
                quads=quads
            )
            self.annotation_manager.add_annotation(annotation)
            current_page_widget.selected_words.clear()
            current_page_widget.selection_rects = []
            self._refresh_current_page()

    def _words_to_quads(self, selected_words):
        quads = []
        lines = {}
        for word_info in selected_words:
            line_key = (word_info[5], word_info[6])
            if line_key not in lines:
                lines[line_key] = []
            lines[line_key].append(word_info)
        
        for line_key, words_in_line in lines.items():
            words_in_line.sort(key=lambda x: x[0])
            min_x = min(word[0] for word in words_in_line)
            max_x = max(word[2] for word in words_in_line)
            min_y = min(word[1] for word in words_in_line)
            max_y = max(word[3] for word in words_in_line)
            quad = [min_x, min_y, max_x, min_y, min_x, max_y, max_x, max_y]
            quads.append(quad)
        return quads

    def _refresh_current_page(self):
        if self.current_page_index in self.loaded_pages:
            self.loaded_pages[self.current_page_index].deleteLater()
            del self.loaded_pages[self.current_page_index]
            self.page_manager.update_visible_pages(self.current_page_index)

    def show_annotation_toolbar(self):
        if self.annotation_toolbar.isVisible():
            self.annotation_toolbar.hide()
        else:
            self.search_bar.hide()
            self.drawing_toolbar.hide()
            self.annotation_toolbar.show()
            self.annotation_toolbar.raise_()

    def _hide_annotation_toolbar(self):
        self.annotation_toolbar.hide()

    def show_drawing_toolbar(self):
        if self.drawing_toolbar.isVisible():
            self.drawing_toolbar.hide()
        else:
            self.search_bar.hide()
            self.annotation_toolbar.hide()
            self.drawing_toolbar.show()
            self.drawing_toolbar.raise_()

    def _hide_drawing_toolbar(self):
        self.drawing_toolbar.hide()
        self.drawing_toolbar._close_toolbar()

    def _on_drawing_mode_changed(self, enabled):
        tool_settings = self.drawing_toolbar.get_current_settings()
        tool, color, stroke_width, filled = tool_settings
        for label in self.loaded_pages.values():
            label.set_drawing_mode(enabled, tool, color, stroke_width, filled)

    def _on_drawing_tool_changed(self, tool, color, stroke_width, filled):
        for label in self.loaded_pages.values():
            label.set_drawing_mode(
                self.drawing_toolbar.is_in_drawing_mode(),
                tool, color, stroke_width, filled
            )
    def undo_annotation(self):
        """Undo the last annotation action."""
        if self.annotation_manager.undo():
            self._refresh_all_visible_pages()
            self._update_undo_redo_buttons()

    def redo_annotation(self):
        """Redo the last undone annotation action."""
        if self.annotation_manager.redo():
            self._refresh_all_visible_pages()
            self._update_undo_redo_buttons()

    def _update_undo_redo_buttons(self):
        """Update the enabled state of undo/redo buttons."""
        if hasattr(self, 'undo_button'):
            self.undo_button.setEnabled(self.annotation_manager.can_undo())
        if hasattr(self, 'redo_button'):
            self.redo_button.setEnabled(self.annotation_manager.can_redo())

    def _refresh_all_visible_pages(self):
        """Refresh all currently visible pages."""
        for idx in list(self.loaded_pages.keys()):
            if idx in self.loaded_pages:
                self.loaded_pages[idx].deleteLater()
                del self.loaded_pages[idx]
        self.update_visible_pages()
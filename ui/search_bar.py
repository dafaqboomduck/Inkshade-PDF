from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QLineEdit,
    QToolButton, QSpacerItem, QSizePolicy
)

class SearchBar(QFrame):
    """Modern search bar for PDF document searching."""
    
    # Signals
    search_requested = pyqtSignal(str)  # Emits search term
    next_result_requested = pyqtSignal()
    prev_result_requested = pyqtSignal()
    close_requested = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("SearchFrame")
        self.setup_ui()
        self.hide()
    
    def setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(8)
        
        # Search input with icon
        self.search_input = QLineEdit(self)
        self.search_input.setPlaceholderText("Search in document...")
        self.search_input.setFixedHeight(32)
        self.search_input.setMinimumWidth(300)
        self.search_input.returnPressed.connect(self._on_search)
        layout.addWidget(self.search_input)

        # Navigation buttons (compact icon style)
        self.prev_button = QToolButton(self)
        self.prev_button.setText("◀")
        self.prev_button.setToolTip("Previous result")
        self.prev_button.setFixedSize(32, 32)
        self.prev_button.clicked.connect(self.prev_result_requested.emit)
        layout.addWidget(self.prev_button)

        self.next_button = QToolButton(self)
        self.next_button.setText("▶")
        self.next_button.setToolTip("Next result")
        self.next_button.setFixedSize(32, 32)
        self.next_button.clicked.connect(self.next_result_requested.emit)
        layout.addWidget(self.next_button)

        # Results status
        self.status_label = QLabel("", self)
        self.status_label.setStyleSheet("color: #8899AA; padding: 0 8px;")
        layout.addWidget(self.status_label)
        
        layout.addSpacerItem(QSpacerItem(10, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))

        # Close button
        self.close_button = QToolButton(self)
        self.close_button.setText("✕")
        self.close_button.setToolTip("Close search")
        self.close_button.setFixedSize(32, 32)
        self.close_button.clicked.connect(self._on_close)
        layout.addWidget(self.close_button)
    
    def _on_search(self):
        """Handle search request."""
        search_term = self.search_input.text()
        self.search_requested.emit(search_term)
    
    def _on_close(self):
        """Handle close request."""
        self.close_requested.emit()
        self.hide()
    
    def show_bar(self):
        """Show the search bar and focus on input."""
        self.show()
        self.search_input.setFocus()
        self.search_input.selectAll()
    
    def set_status(self, text):
        """Update the status label."""
        self.status_label.setText(text)
    
    def clear_search(self):
        """Clear the search input and status."""
        self.search_input.clear()
        self.status_label.setText("")
    
    def get_search_text(self):
        """Get the current search text."""
        return self.search_input.text()
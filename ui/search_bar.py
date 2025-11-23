from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QToolButton, QWidget, QGraphicsDropShadowEffect, QSizePolicy
)
from PyQt5.QtGui import QColor


class SearchBar(QFrame):
    """Compact modern search bar that appears on the right side."""
    
    # Signals
    search_requested = pyqtSignal(str)
    next_result_requested = pyqtSignal()
    prev_result_requested = pyqtSignal()
    close_requested = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("SearchBar")
        self.setup_ui()
        self.hide()
    
    def setup_ui(self):
        # Set fixed width and let height expand naturally
        self.setFixedWidth(300)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 10, 12, 10)
        main_layout.setSpacing(8)
        
        # Header with close button
        header_layout = QHBoxLayout()
        header_layout.setSpacing(8)
        
        header_label = QLabel("Search", self)
        header_label.setStyleSheet("font-weight: bold; color: #8899AA;")
        header_layout.addWidget(header_label)
        
        header_layout.addStretch()
        
        self.close_button = QToolButton(self)
        self.close_button.setText("✕")
        self.close_button.setToolTip("Close search")
        self.close_button.setFixedSize(24, 24)
        self.close_button.clicked.connect(self._on_close)
        header_layout.addWidget(self.close_button)
        
        main_layout.addLayout(header_layout)
        
        # Search input
        self.search_input = QLineEdit(self)
        self.search_input.setPlaceholderText("Search in document...")
        self.search_input.setFixedHeight(32)
        self.search_input.returnPressed.connect(self._on_search)
        main_layout.addWidget(self.search_input)
        
        # Navigation and status
        nav_layout = QHBoxLayout()
        nav_layout.setSpacing(6)
        
        self.prev_button = QToolButton(self)
        self.prev_button.setText("◀")
        self.prev_button.setToolTip("Previous")
        self.prev_button.setFixedSize(28, 28)
        self.prev_button.clicked.connect(self.prev_result_requested.emit)
        nav_layout.addWidget(self.prev_button)
        
        self.next_button = QToolButton(self)
        self.next_button.setText("▶")
        self.next_button.setToolTip("Next")
        self.next_button.setFixedSize(28, 28)
        self.next_button.clicked.connect(self.next_result_requested.emit)
        nav_layout.addWidget(self.next_button)
        
        self.status_label = QLabel("", self)
        self.status_label.setStyleSheet("color: #8899AA; font-size: 12px;")
        nav_layout.addWidget(self.status_label)
        nav_layout.addStretch()
        
        main_layout.addLayout(nav_layout)
        
        # Let the layout calculate natural size
        self.adjustSize()
        
        # Add shadow effect for better visibility
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(20)
        shadow.setColor(QColor(0, 0, 0, 80))
        shadow.setOffset(0, 2)
        self.setGraphicsEffect(shadow)
    
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
        self.raise_()
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
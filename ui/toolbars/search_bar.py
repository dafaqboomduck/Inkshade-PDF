from PyQt5.QtCore import QEvent, Qt, pyqtSignal
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import (
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
)


class SearchLineEdit(QLineEdit):
    """
    Custom QLineEdit that intercepts Tab/Shift+Tab for search navigation.

    Note: Tab MUST be handled at the widget level because Qt intercepts it
    for focus navigation before it reaches keyPressEvent or the main window.
    """

    navigate_next = pyqtSignal()
    navigate_prev = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)

    def event(self, event: QEvent) -> bool:
        """Intercept Tab before Qt's focus handling."""
        if event.type() == QEvent.KeyPress:
            key = event.key()

            if key == Qt.Key_Tab:
                self.navigate_next.emit()
                return True
            elif key == Qt.Key_Backtab:
                self.navigate_prev.emit()
                return True

        return super().event(event)


class SearchBar(QFrame):
    """Compact modern search bar that appears on the right side."""

    search_requested = pyqtSignal(str)
    next_result_requested = pyqtSignal()
    prev_result_requested = pyqtSignal()
    close_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("SearchBar")
        self._last_search_term = ""
        self._has_results = False
        self.setup_ui()
        self.hide()

    def setup_ui(self):
        self.setFixedWidth(300)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 10, 12, 10)
        main_layout.setSpacing(8)

        # Header
        header_layout = QHBoxLayout()
        header_layout.setSpacing(8)

        header_label = QLabel("Search", self)
        header_label.setStyleSheet("font-weight: bold; color: #8899AA;")
        header_layout.addWidget(header_label)
        header_layout.addStretch()

        self.close_button = QToolButton(self)
        self.close_button.setText("✕")
        self.close_button.setToolTip("Close (Esc)")
        self.close_button.setFixedSize(24, 24)
        self.close_button.clicked.connect(self._on_close)
        header_layout.addWidget(self.close_button)

        main_layout.addLayout(header_layout)

        # Search input
        self.search_input = SearchLineEdit(self)
        self.search_input.setPlaceholderText("Search in document...")
        self.search_input.setFixedHeight(32)
        self.search_input.returnPressed.connect(self._on_enter_pressed)
        self.search_input.textChanged.connect(self._on_text_changed)
        self.search_input.navigate_next.connect(self._on_navigate_next)
        self.search_input.navigate_prev.connect(self._on_navigate_prev)
        main_layout.addWidget(self.search_input)

        # Navigation
        nav_layout = QHBoxLayout()
        nav_layout.setSpacing(6)

        self.prev_button = QToolButton(self)
        self.prev_button.setText("◀")
        self.prev_button.setToolTip("Previous (Shift+Tab, Shift+F3)")
        self.prev_button.setFixedSize(28, 28)
        self.prev_button.clicked.connect(self._on_navigate_prev)
        nav_layout.addWidget(self.prev_button)

        self.next_button = QToolButton(self)
        self.next_button.setText("▶")
        self.next_button.setToolTip("Next (Tab, Enter, F3)")
        self.next_button.setFixedSize(28, 28)
        self.next_button.clicked.connect(self._on_navigate_next)
        nav_layout.addWidget(self.next_button)

        self.status_label = QLabel("", self)
        self.status_label.setStyleSheet("color: #8899AA; font-size: 12px;")
        nav_layout.addWidget(self.status_label)
        nav_layout.addStretch()

        main_layout.addLayout(nav_layout)
        self.adjustSize()

        # Shadow
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(20)
        shadow.setColor(QColor(0, 0, 0, 80))
        shadow.setOffset(0, 2)
        self.setGraphicsEffect(shadow)

    def _on_enter_pressed(self):
        """Handle Enter: search if new term, else navigate next."""
        search_term = self.search_input.text().strip()
        if not search_term:
            return

        if search_term != self._last_search_term or not self._has_results:
            self._last_search_term = search_term
            self._has_results = False
            self.search_requested.emit(search_term)
        else:
            self.next_result_requested.emit()

    def _on_navigate_next(self):
        """Navigate to next result, or search first if needed."""
        search_term = self.search_input.text().strip()
        if not search_term:
            return

        if search_term != self._last_search_term or not self._has_results:
            self._last_search_term = search_term
            self._has_results = False
            self.search_requested.emit(search_term)
        else:
            self.next_result_requested.emit()

    def _on_navigate_prev(self):
        """Navigate to previous result, or search first if needed."""
        search_term = self.search_input.text().strip()
        if not search_term:
            return

        if search_term != self._last_search_term or not self._has_results:
            self._last_search_term = search_term
            self._has_results = False
            self.search_requested.emit(search_term)
        else:
            self.prev_result_requested.emit()

    def _on_text_changed(self, text: str):
        """Reset state when search text changes."""
        if text.strip() != self._last_search_term:
            self._has_results = False

    def _on_close(self):
        """Close the search bar."""
        self.close_requested.emit()
        self.hide()

    def show_bar(self):
        """Show and focus the search bar."""
        self.show()
        self.raise_()
        self.search_input.setFocus()
        self.search_input.selectAll()

    def set_status(self, text: str):
        """Update status and track if we have results."""
        self.status_label.setText(text)
        if text and " of " in text:
            self._has_results = True
        elif text in ("0 results", "Searching..."):
            self._has_results = False

    def clear_search(self):
        """Clear search state."""
        self.search_input.clear()
        self.status_label.setText("")
        self._last_search_term = ""
        self._has_results = False

    def get_search_text(self) -> str:
        """Get current search text."""
        return self.search_input.text()

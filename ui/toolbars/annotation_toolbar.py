from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel, 
    QColorDialog, QToolButton, QWidget, QGraphicsDropShadowEffect, QSizePolicy
)
from core.annotations import AnnotationType


class AnnotationToolbar(QFrame):
    """Compact annotation toolbar with simplified highlight-only functionality."""
    
    annotation_requested = pyqtSignal(AnnotationType, tuple)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("AnnotationToolbar")
        self.current_color = (255, 255, 0)  # Default yellow for highlight
        self.current_type = AnnotationType.HIGHLIGHT  # Fixed to highlight only
        
        self.setup_ui()
        self.hide()
    
    def setup_ui(self):
        # Set fixed width and let height expand naturally
        self.setFixedWidth(300)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 10, 12, 10)
        main_layout.setSpacing(8)
        
        # Header
        header_layout = QHBoxLayout()
        header_layout.setSpacing(8)
        
        header_label = QLabel("Highlight Text", self)
        header_label.setStyleSheet("font-weight: bold; color: #8899AA;")
        header_layout.addWidget(header_label)
        
        header_layout.addStretch()
        
        self.close_button = QToolButton(self)
        self.close_button.setText("✕")
        self.close_button.setToolTip("Close")
        self.close_button.setFixedSize(24, 24)
        self.close_button.clicked.connect(self.hide)
        header_layout.addWidget(self.close_button)
        
        main_layout.addLayout(header_layout)
        
        # Info label
        info_label = QLabel("Select text first, then apply highlight", self)
        info_label.setStyleSheet("color: #8899AA; font-size: 11px;")
        info_label.setWordWrap(True)
        main_layout.addWidget(info_label)
        
        # Color picker
        color_layout = QHBoxLayout()
        color_layout.setSpacing(8)
        
        color_label = QLabel("Color:", self)
        color_label.setStyleSheet("color: #8899AA;")
        color_layout.addWidget(color_label)
        
        self.color_button = QToolButton(self)
        self.color_button.setToolTip("Choose color")
        self.color_button.setFixedSize(40, 40)
        self.color_button.clicked.connect(self._choose_color)
        self._update_color_button()
        color_layout.addWidget(self.color_button)
        
        color_layout.addStretch()
        
        main_layout.addLayout(color_layout)
        
        # Apply button
        self.apply_button = QToolButton(self)
        self.apply_button.setText("Apply Highlight")
        self.apply_button.setFixedHeight(36)
        self.apply_button.clicked.connect(self._on_apply)
        self.apply_button.setStyleSheet("""
            QToolButton {
                background-color: #4a9eff;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 0 12px;
                font-weight: bold;
            }
            QToolButton:hover {
                background-color: #3a8eef;
            }
            QToolButton:pressed {
                background-color: #2a7edf;
            }
        """)
        main_layout.addWidget(self.apply_button)
        
        # Let the layout calculate natural size
        self.adjustSize()
        
        # Add shadow
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(20)
        shadow.setColor(QColor(0, 0, 0, 80))
        shadow.setOffset(0, 2)
        self.setGraphicsEffect(shadow)
    
    def _choose_color(self):
        """Open color picker dialog."""
        initial_color = QColor(self.current_color[0], self.current_color[1], self.current_color[2])
        color = QColorDialog.getColor(initial_color, self, "Choose Highlight Color")
        
        if color.isValid():
            self.current_color = (color.red(), color.green(), color.blue())
            self._update_color_button()
    
    def _update_color_button(self):
        """Update the color button to show the current color."""
        r, g, b = self.current_color
        self.color_button.setStyleSheet(f"""
            QToolButton {{
                background-color: rgb({r}, {g}, {b});
                border: 2px solid #555555;
                border-radius: 4px;
            }}
            QToolButton:hover {{
                border: 2px solid #777777;
            }}
        """)
    
    def _on_apply(self):
        """Emit signal to create highlight annotation with current color."""
        self.annotation_requested.emit(AnnotationType.HIGHLIGHT, self.current_color)
        self.hide()
    
    def get_current_settings(self):
        """Return current annotation type and color."""
        return AnnotationType.HIGHLIGHT, self.current_color
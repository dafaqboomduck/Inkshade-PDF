from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import (
    QFrame, QHBoxLayout, QPushButton, QLabel, 
    QColorDialog, QButtonGroup, QRadioButton
)
from helpers.annotations import AnnotationType


class AnnotationToolbar(QFrame):
    """Toolbar for creating annotations on selected text."""
    
    # Signal emitted when user wants to create an annotation
    annotation_requested = pyqtSignal(AnnotationType, tuple)  # (type, color)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("AnnotationToolbar")
        self.current_color = (255, 255, 0)  # Default: Yellow
        self.current_type = AnnotationType.HIGHLIGHT
        
        self.setup_ui()
        self.hide()  # Start hidden
    
    def setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 5, 10, 5)
        layout.setSpacing(10)
        
        # Annotation type selector
        type_label = QLabel("Type:", self)
        layout.addWidget(type_label)
        
        self.highlight_radio = QRadioButton("Highlight", self)
        self.highlight_radio.setChecked(True)
        self.highlight_radio.toggled.connect(self._on_type_changed)
        layout.addWidget(self.highlight_radio)
        
        self.underline_radio = QRadioButton("Underline", self)
        self.underline_radio.toggled.connect(self._on_type_changed)
        layout.addWidget(self.underline_radio)
        
        # Color picker button
        self.color_button = QPushButton("Color", self)
        self.color_button.clicked.connect(self._choose_color)
        self._update_color_button_style()
        layout.addWidget(self.color_button)
        
        # Apply button
        self.apply_button = QPushButton("Apply", self)
        self.apply_button.clicked.connect(self._on_apply)
        layout.addWidget(self.apply_button)
        
        # Cancel button
        self.cancel_button = QPushButton("Cancel", self)
        self.cancel_button.clicked.connect(self.hide)
        layout.addWidget(self.cancel_button)
    
    def _on_type_changed(self):
        """Update current annotation type based on radio button selection."""
        if self.highlight_radio.isChecked():
            self.current_type = AnnotationType.HIGHLIGHT
        else:
            self.current_type = AnnotationType.UNDERLINE
    
    def _choose_color(self):
        """Open color picker dialog."""
        initial_color = QColor(self.current_color[0], self.current_color[1], self.current_color[2])
        color = QColorDialog.getColor(initial_color, self, "Choose Annotation Color")
        
        if color.isValid():
            self.current_color = (color.red(), color.green(), color.blue())
            self._update_color_button_style()
    
    def _update_color_button_style(self):
        """Update the color button to show the current color."""
        r, g, b = self.current_color
        self.color_button.setStyleSheet(f"""
            QPushButton {{
                background-color: rgb({r}, {g}, {b});
                color: {'#000000' if (r + g + b) > 384 else '#ffffff'};
                border: 2px solid #555555;
                border-radius: 4px;
                padding: 6px 12px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                border: 2px solid #777777;
            }}
        """)
    
    def _on_apply(self):
        """Emit signal to create annotation with current settings."""
        self.annotation_requested.emit(self.current_type, self.current_color)
        self.hide()
    
    def get_current_settings(self):
        """Return current annotation type and color."""
        return self.current_type, self.current_color
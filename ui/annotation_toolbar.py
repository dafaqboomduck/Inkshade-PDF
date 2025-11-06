from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel, 
    QColorDialog, QToolButton, QWidget, QGraphicsDropShadowEffect, QSizePolicy
)
from helpers.annotations import AnnotationType


class AnnotationToolbar(QFrame):
    """Compact annotation toolbar that appears on the right side."""
    
    annotation_requested = pyqtSignal(AnnotationType, tuple)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("AnnotationToolbar")
        self.current_color = (255, 255, 0)
        self.current_type = AnnotationType.HIGHLIGHT
        
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
        
        header_label = QLabel("Annotate", self)
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
        
        # Type selection
        type_layout = QHBoxLayout()
        type_layout.setSpacing(6)
        
        self.highlight_button = QToolButton(self)
        self.highlight_button.setText("🖍")
        self.highlight_button.setToolTip("Highlight")
        self.highlight_button.setCheckable(True)
        self.highlight_button.setChecked(True)
        self.highlight_button.setFixedSize(40, 40)
        self.highlight_button.clicked.connect(lambda: self._set_type(AnnotationType.HIGHLIGHT))
        type_layout.addWidget(self.highlight_button)
        
        self.underline_button = QToolButton(self)
        self.underline_button.setText("U̲")
        self.underline_button.setToolTip("Underline")
        self.underline_button.setCheckable(True)
        self.underline_button.setFixedSize(40, 40)
        self.underline_button.clicked.connect(lambda: self._set_type(AnnotationType.UNDERLINE))
        type_layout.addWidget(self.underline_button)
        
        type_layout.addStretch()
        
        main_layout.addLayout(type_layout)
        
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
        self.apply_button.setText("Apply Annotation")
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
    
    def _set_type(self, annotation_type):
        """Update current annotation type and button states."""
        self.current_type = annotation_type
        self.highlight_button.setChecked(annotation_type == AnnotationType.HIGHLIGHT)
        self.underline_button.setChecked(annotation_type == AnnotationType.UNDERLINE)
    
    def _choose_color(self):
        """Open color picker dialog."""
        initial_color = QColor(self.current_color[0], self.current_color[1], self.current_color[2])
        color = QColorDialog.getColor(initial_color, self, "Choose Annotation Color")
        
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
        """Emit signal to create annotation with current settings."""
        self.annotation_requested.emit(self.current_type, self.current_color)
        self.hide()
    
    def get_current_settings(self):
        """Return current annotation type and color."""
        return self.current_type, self.current_color
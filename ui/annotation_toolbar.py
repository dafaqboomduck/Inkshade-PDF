from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, 
    QColorDialog, QToolButton, QSpacerItem, QSizePolicy
)
from helpers.annotations import AnnotationType


class AnnotationToolbar(QFrame):
    """Modern toolbar for creating annotations on selected text."""
    
    annotation_requested = pyqtSignal(AnnotationType, tuple)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("AnnotationToolbar")
        self.current_color = (255, 255, 0)
        self.current_type = AnnotationType.HIGHLIGHT
        
        self.setup_ui()
        self.hide()
    
    def setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(8)
        
        # Title
        title_label = QLabel("Annotate:", self)
        title_label.setStyleSheet("font-weight: bold; color: #8899AA;")
        layout.addWidget(title_label)
        
        layout.addSpacerItem(QSpacerItem(10, 20, QSizePolicy.Fixed, QSizePolicy.Minimum))
        
        # Highlight button
        self.highlight_button = QToolButton(self)
        self.highlight_button.setText("🖍")
        self.highlight_button.setToolTip("Highlight")
        self.highlight_button.setCheckable(True)
        self.highlight_button.setChecked(True)
        self.highlight_button.setFixedSize(36, 36)
        self.highlight_button.clicked.connect(lambda: self._set_type(AnnotationType.HIGHLIGHT))
        layout.addWidget(self.highlight_button)
        
        # Underline button
        self.underline_button = QToolButton(self)
        self.underline_button.setText("U̲")
        self.underline_button.setToolTip("Underline")
        self.underline_button.setCheckable(True)
        self.underline_button.setFixedSize(36, 36)
        self.underline_button.clicked.connect(lambda: self._set_type(AnnotationType.UNDERLINE))
        layout.addWidget(self.underline_button)
        
        layout.addSpacerItem(QSpacerItem(15, 20, QSizePolicy.Fixed, QSizePolicy.Minimum))
        
        # Color picker
        self.color_button = QToolButton(self)
        self.color_button.setToolTip("Choose color")
        self.color_button.setFixedSize(36, 36)
        self.color_button.clicked.connect(self._choose_color)
        self._update_color_button()
        layout.addWidget(self.color_button)
        
        layout.addSpacerItem(QSpacerItem(10, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))
        
        # Apply button
        self.apply_button = QToolButton(self)
        self.apply_button.setText("Apply")
        self.apply_button.setToolTip("Apply annotation")
        self.apply_button.setFixedHeight(36)
        self.apply_button.setMinimumWidth(70)
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
        layout.addWidget(self.apply_button)
        
        # Close button
        self.cancel_button = QToolButton(self)
        self.cancel_button.setText("✕")
        self.cancel_button.setToolTip("Close")
        self.cancel_button.setFixedSize(32, 32)
        self.cancel_button.clicked.connect(self.hide)
        layout.addWidget(self.cancel_button)
    
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
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import (
    QFrame, QHBoxLayout, QPushButton, QLabel, 
    QColorDialog, QButtonGroup, QRadioButton, QSpinBox, QCheckBox
)
from helpers.annotations import AnnotationType


class DrawingToolbar(QFrame):
    """Toolbar for drawing shapes and freehand annotations."""
    
    # Signal emitted when drawing mode changes
    drawing_mode_changed = pyqtSignal(bool)  # True when entering drawing mode, False when exiting
    
    # Signal emitted when tool settings change
    tool_changed = pyqtSignal(AnnotationType, tuple, float, bool)  # (type, color, stroke_width, filled)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("DrawingToolbar")
        self.current_color = (255, 0, 0)  # Default: Red
        self.current_stroke_width = 2.0
        self.current_filled = False
        self.current_tool = AnnotationType.FREEHAND
        self.is_drawing_mode = False
        
        self.setup_ui()
        self.hide()  # Start hidden
    
    def setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 5, 10, 5)
        layout.setSpacing(10)
        
        # Drawing mode toggle
        self.mode_button = QPushButton("Start Drawing", self)
        self.mode_button.setCheckable(True)
        self.mode_button.clicked.connect(self._toggle_drawing_mode)
        layout.addWidget(self.mode_button)
        
        # Separator
        separator1 = QFrame()
        separator1.setFrameShape(QFrame.VLine)
        separator1.setFrameShadow(QFrame.Sunken)
        layout.addWidget(separator1)
        
        # Tool type selector
        tool_label = QLabel("Tool:", self)
        layout.addWidget(tool_label)
        
        self.freehand_radio = QRadioButton("Freehand", self)
        self.freehand_radio.setChecked(True)
        self.freehand_radio.toggled.connect(self._on_tool_changed)
        layout.addWidget(self.freehand_radio)
        
        self.line_radio = QRadioButton("Line", self)
        self.line_radio.toggled.connect(self._on_tool_changed)
        layout.addWidget(self.line_radio)
        
        self.arrow_radio = QRadioButton("Arrow", self)
        self.arrow_radio.toggled.connect(self._on_tool_changed)
        layout.addWidget(self.arrow_radio)
        
        self.rect_radio = QRadioButton("Rectangle", self)
        self.rect_radio.toggled.connect(self._on_tool_changed)
        layout.addWidget(self.rect_radio)
        
        self.circle_radio = QRadioButton("Circle", self)
        self.circle_radio.toggled.connect(self._on_tool_changed)
        layout.addWidget(self.circle_radio)
        
        # Separator
        separator2 = QFrame()
        separator2.setFrameShape(QFrame.VLine)
        separator2.setFrameShadow(QFrame.Sunken)
        layout.addWidget(separator2)
        
        # Stroke width
        stroke_label = QLabel("Width:", self)
        layout.addWidget(stroke_label)
        
        self.stroke_spinbox = QSpinBox(self)
        self.stroke_spinbox.setMinimum(1)
        self.stroke_spinbox.setMaximum(20)
        self.stroke_spinbox.setValue(2)
        self.stroke_spinbox.valueChanged.connect(self._on_stroke_changed)
        layout.addWidget(self.stroke_spinbox)
        
        # Filled checkbox
        self.filled_checkbox = QCheckBox("Filled", self)
        self.filled_checkbox.stateChanged.connect(self._on_filled_changed)
        layout.addWidget(self.filled_checkbox)
        
        # Color picker button
        self.color_button = QPushButton("Color", self)
        self.color_button.clicked.connect(self._choose_color)
        self._update_color_button_style()
        layout.addWidget(self.color_button)
        
        # Close button
        self.close_button = QPushButton("Close", self)
        self.close_button.clicked.connect(self._close_toolbar)
        layout.addWidget(self.close_button)
    
    def _toggle_drawing_mode(self):
        """Toggle between drawing mode and normal mode."""
        self.is_drawing_mode = self.mode_button.isChecked()
        
        if self.is_drawing_mode:
            self.mode_button.setText("Stop Drawing")
            self.mode_button.setStyleSheet("background-color: #ff6666;")
        else:
            self.mode_button.setText("Start Drawing")
            self.mode_button.setStyleSheet("")
        
        self.drawing_mode_changed.emit(self.is_drawing_mode)
    
    def _on_tool_changed(self):
        """Update current tool based on radio button selection."""
        if self.freehand_radio.isChecked():
            self.current_tool = AnnotationType.FREEHAND
            self.filled_checkbox.setEnabled(False)
        elif self.line_radio.isChecked():
            self.current_tool = AnnotationType.LINE
            self.filled_checkbox.setEnabled(False)
        elif self.arrow_radio.isChecked():
            self.current_tool = AnnotationType.ARROW
            self.filled_checkbox.setEnabled(False)
        elif self.rect_radio.isChecked():
            self.current_tool = AnnotationType.RECTANGLE
            self.filled_checkbox.setEnabled(True)
        elif self.circle_radio.isChecked():
            self.current_tool = AnnotationType.CIRCLE
            self.filled_checkbox.setEnabled(True)
        
        self._emit_tool_changed()
    
    def _on_stroke_changed(self, value):
        """Update stroke width."""
        self.current_stroke_width = float(value)
        self._emit_tool_changed()
    
    def _on_filled_changed(self, state):
        """Update filled state."""
        self.current_filled = (state == Qt.Checked)
        self._emit_tool_changed()
    
    def _choose_color(self):
        """Open color picker dialog."""
        initial_color = QColor(self.current_color[0], self.current_color[1], self.current_color[2])
        color = QColorDialog.getColor(initial_color, self, "Choose Drawing Color")
        
        if color.isValid():
            self.current_color = (color.red(), color.green(), color.blue())
            self._update_color_button_style()
            self._emit_tool_changed()
    
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
    
    def _emit_tool_changed(self):
        """Emit signal with current tool settings."""
        self.tool_changed.emit(
            self.current_tool, 
            self.current_color, 
            self.current_stroke_width,
            self.current_filled
        )
    
    def _close_toolbar(self):
        """Close toolbar and exit drawing mode."""
        if self.is_drawing_mode:
            self.mode_button.setChecked(False)
            self._toggle_drawing_mode()
        self.hide()
    
    def get_current_settings(self):
        """Return current tool settings."""
        return (self.current_tool, self.current_color, self.current_stroke_width, self.current_filled)
    
    def is_in_drawing_mode(self):
        """Check if currently in drawing mode."""
        return self.is_drawing_mode
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel, 
    QColorDialog, QToolButton, QSpinBox, QCheckBox, QWidget,
    QGraphicsDropShadowEffect, QSizePolicy
)
from helpers.annotations import AnnotationType


class DrawingToolbar(QFrame):
    """Compact drawing toolbar that appears on the right side."""
    
    drawing_mode_changed = pyqtSignal(bool)
    tool_changed = pyqtSignal(AnnotationType, tuple, float, bool)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("DrawingToolbar")
        self.current_color = (255, 0, 0)
        self.current_stroke_width = 2.0
        self.current_filled = False
        self.current_tool = AnnotationType.FREEHAND
        self.is_drawing_mode = False
        
        self.setup_ui()
        self.hide()
    
    def setup_ui(self):
        # Set fixed width and let height expand naturally
        self.setFixedWidth(300)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 10, 12, 10)
        main_layout.setSpacing(10)
        
        # Header
        header_layout = QHBoxLayout()
        header_layout.setSpacing(8)
        
        header_label = QLabel("Draw", self)
        header_label.setStyleSheet("font-weight: bold; color: #8899AA;")
        header_layout.addWidget(header_label)
        
        header_layout.addStretch()
        
        self.close_button = QToolButton(self)
        self.close_button.setText("✕")
        self.close_button.setToolTip("Close toolbar")
        self.close_button.setFixedSize(24, 24)
        self.close_button.clicked.connect(self._close_toolbar)
        header_layout.addWidget(self.close_button)
        
        main_layout.addLayout(header_layout)
        
        # Drawing mode toggle
        self.mode_button = QToolButton(self)
        self.mode_button.setText("Start Drawing")
        self.mode_button.setCheckable(True)
        self.mode_button.setFixedHeight(36)
        self.mode_button.clicked.connect(self._toggle_drawing_mode)
        self.mode_button.setStyleSheet("""
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
            QToolButton:checked {
                background-color: #ff6b6b;
            }
            QToolButton:checked:hover {
                background-color: #ff5252;
            }
        """)
        main_layout.addWidget(self.mode_button)
        
        # Tool selection
        tools_label = QLabel("Tools", self)
        tools_label.setStyleSheet("color: #8899AA; font-size: 11px; margin-top: 4px;")
        main_layout.addWidget(tools_label)
        
        # Tool buttons - First row
        tool_row1 = QHBoxLayout()
        tool_row1.setSpacing(6)
        
        self.tool_buttons = []
        
        self.freehand_button = self._create_tool_button("✏️", "Freehand", AnnotationType.FREEHAND, True)
        tool_row1.addWidget(self.freehand_button)
        
        self.line_button = self._create_tool_button("—", "Line", AnnotationType.LINE, False)
        tool_row1.addWidget(self.line_button)
        
        self.arrow_button = self._create_tool_button("→", "Arrow", AnnotationType.ARROW, False)
        tool_row1.addWidget(self.arrow_button)

        self.rect_button = self._create_tool_button("□", "Rectangle", AnnotationType.RECTANGLE, False)
        tool_row1.addWidget(self.rect_button)
        
        self.circle_button = self._create_tool_button("○", "Circle", AnnotationType.CIRCLE, False)
        tool_row1.addWidget(self.circle_button)
        
        main_layout.addLayout(tool_row1)
        
        # Settings
        settings_label = QLabel("Settings", self)
        settings_label.setStyleSheet("color: #8899AA; font-size: 11px; margin-top: 4px;")
        main_layout.addWidget(settings_label)
        
        # Stroke width
        width_layout = QHBoxLayout()
        width_layout.setSpacing(8)
        
        width_label = QLabel("Width:", self)
        width_label.setStyleSheet("color: #B5B5C5;")
        width_layout.addWidget(width_label)
        
        self.stroke_spinbox = QSpinBox(self)
        self.stroke_spinbox.setMinimum(1)
        self.stroke_spinbox.setMaximum(20)
        self.stroke_spinbox.setValue(2)
        self.stroke_spinbox.setFixedWidth(70)
        self.stroke_spinbox.setFixedHeight(28)
        self.stroke_spinbox.valueChanged.connect(self._on_stroke_changed)
        width_layout.addWidget(self.stroke_spinbox)
        
        width_layout.addStretch()
        
        main_layout.addLayout(width_layout)
        
        # Fill option
        self.filled_checkbox = QCheckBox("Fill shapes", self)
        self.filled_checkbox.setEnabled(False)
        self.filled_checkbox.stateChanged.connect(self._on_filled_changed)
        main_layout.addWidget(self.filled_checkbox)
        
        # Color picker
        color_layout = QHBoxLayout()
        color_layout.setSpacing(8)
        
        color_label = QLabel("Color:", self)
        color_label.setStyleSheet("color: #B5B5C5;")
        color_layout.addWidget(color_label)
        
        self.color_button = QToolButton(self)
        self.color_button.setToolTip("Choose color")
        self.color_button.setFixedSize(40, 40)
        self.color_button.clicked.connect(self._choose_color)
        self._update_color_button()
        color_layout.addWidget(self.color_button)
        
        color_layout.addStretch()
        
        main_layout.addLayout(color_layout)
        
        # Let the layout calculate natural size
        self.adjustSize()
        
        # Add shadow
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(20)
        shadow.setColor(QColor(0, 0, 0, 80))
        shadow.setOffset(0, 2)
        self.setGraphicsEffect(shadow)
    
    def _create_tool_button(self, icon, tooltip, tool_type, checked):
        """Create a tool selection button."""
        btn = QToolButton(self)
        btn.setText(icon)
        btn.setToolTip(tooltip)
        btn.setCheckable(True)
        btn.setChecked(checked)
        btn.setFixedSize(40, 40)
        btn.clicked.connect(lambda: self._select_tool(tool_type, btn))
        self.tool_buttons.append((btn, tool_type))
        return btn
    
    def _select_tool(self, tool_type, button):
        """Select a drawing tool."""
        self.current_tool = tool_type
        
        # Update button states
        for btn, _ in self.tool_buttons:
            btn.setChecked(btn == button)
        
        # Enable/disable fill option for shapes
        can_fill = tool_type in [AnnotationType.RECTANGLE, AnnotationType.CIRCLE, AnnotationType.FREEHAND]
        self.filled_checkbox.setEnabled(can_fill)
        
        self._emit_tool_changed()
    
    def _toggle_drawing_mode(self):
        """Toggle between drawing mode and normal mode."""
        self.is_drawing_mode = self.mode_button.isChecked()
        
        if self.is_drawing_mode:
            self.mode_button.setText("Stop Drawing")
        else:
            self.mode_button.setText("Start Drawing")
        
        self.drawing_mode_changed.emit(self.is_drawing_mode)
    
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
            self._update_color_button()
            self._emit_tool_changed()
    
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
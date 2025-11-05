from PyQt5.QtWidgets import QWidget

def apply_style(widget: QWidget, dark_mode: bool):
    """
    Applies a modern style sheet to the main window and its widgets,
    retaining a classic dark and light mode color scheme.
    """
    if dark_mode:
        style_sheet = """
            /* --- GENERAL STYLES (DARK MODE) --- */
            QMainWindow, QWidget, QLineEdit, QLabel, QFrame {
                background-color: #2e2e2e;
                color: #f0f0f0;
                border: none;
            }

            /* --- BUTTONS --- */
            QPushButton {
                background-color: #4e4e4e;
                color: #f0f0f0;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #5a5a5a;
            }
            QPushButton:pressed {
                background-color: #3b3b3b;
            }

            /* --- TOOL BUTTONS --- */
            QToolButton {
                background-color: transparent;
                color: #B5B5C5;
                border: none;
                border-radius: 4px;
                padding: 4px;
            }
            QToolButton:hover {
                background-color: #3e3e3e;
            }
            QToolButton:pressed {
                background-color: #2e2e2e;
            }
            QToolButton:checked {
                background-color: #4a9eff;
                color: white;
            }
            QToolButton:checked:hover {
                background-color: #3a8eef;
            }

            /* --- INPUTS AND LABELS --- */
            QLineEdit {
                background-color: #3e3e3e;
                border: 1px solid #555555;
                border-radius: 6px;
                padding: 6px 10px;
                color: #f0f0f0;
            }
            QLineEdit:focus {
                border: 1px solid #4a9eff;
            }
            
            QLineEdit[objectName="page_input"], QLineEdit[objectName="zoom_input"] {
                min-width: 60px;
                max-width: 60px;
                text-align: center;
            }
            
            QLabel {
                background-color: transparent;
            }

            /* --- SPINBOX --- */
            QSpinBox {
                background-color: #3e3e3e;
                border: 1px solid #555555;
                border-radius: 4px;
                padding: 4px 8px;
                color: #f0f0f0;
            }
            QSpinBox:focus {
                border: 1px solid #4a9eff;
            }
            QSpinBox::up-button, QSpinBox::down-button {
                background-color: #4e4e4e;
                border: none;
                border-radius: 2px;
            }
            QSpinBox::up-button:hover, QSpinBox::down-button:hover {
                background-color: #5a5a5a;
            }

            /* --- CHECKBOX --- */
            QCheckBox {
                color: #f0f0f0;
                spacing: 6px;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border: 2px solid #555555;
                border-radius: 3px;
                background-color: #3e3e3e;
            }
            QCheckBox::indicator:checked {
                background-color: #4a9eff;
                border-color: #4a9eff;
            }
            QCheckBox::indicator:hover {
                border-color: #777777;
            }

            /* --- FRAMES & SEPARATORS --- */
            #TopFrame, #SearchFrame, #AnnotationToolbar, #DrawingToolbar {
                background-color: #2e2e2e;
                border-bottom: 1px solid #3e3e3e;
            }

            QScrollArea {
                background-color: #2e2e2e;
                border: none;
            }
        """
    else: # Light Mode
        style_sheet = """
            /* --- GENERAL STYLES (LIGHT MODE) --- */
            QMainWindow, QWidget, QLineEdit, QLabel, QFrame {
                background-color: #f0f0f0;
                color: #2e2e2e;
                border: none;
            }

            /* --- BUTTONS --- */
            QPushButton {
                background-color: #e0e0e0;
                color: #2e2e2e;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #d0d0d0;
            }
            QPushButton:pressed {
                background-color: #c0c0c0;
            }

            /* --- TOOL BUTTONS --- */
            QToolButton {
                background-color: transparent;
                color: #7A899C;
                border: none;
                border-radius: 4px;
                padding: 4px;
            }
            QToolButton:hover {
                background-color: #e6e6e6;
            }
            QToolButton:pressed {
                background-color: #d6d6d6;
            }
            QToolButton:checked {
                background-color: #4a9eff;
                color: white;
            }
            QToolButton:checked:hover {
                background-color: #3a8eef;
            }

            /* --- INPUTS AND LABELS --- */
            QLineEdit {
                background-color: #ffffff;
                border: 1px solid #cccccc;
                border-radius: 6px;
                padding: 6px 10px;
                color: #2e2e2e;
            }
            QLineEdit:focus {
                border: 1px solid #4a9eff;
            }
            
            QLineEdit[objectName="page_input"], QLineEdit[objectName="zoom_input"] {
                min-width: 60px;
                max-width: 60px;
                text-align: center;
            }
            
            QLabel {
                background-color: transparent;
            }

            /* --- SPINBOX --- */
            QSpinBox {
                background-color: #ffffff;
                border: 1px solid #cccccc;
                border-radius: 4px;
                padding: 4px 8px;
                color: #2e2e2e;
            }
            QSpinBox:focus {
                border: 1px solid #4a9eff;
            }
            QSpinBox::up-button, QSpinBox::down-button {
                background-color: #e0e0e0;
                border: none;
                border-radius: 2px;
            }
            QSpinBox::up-button:hover, QSpinBox::down-button:hover {
                background-color: #d0d0d0;
            }

            /* --- CHECKBOX --- */
            QCheckBox {
                color: #2e2e2e;
                spacing: 6px;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border: 2px solid #cccccc;
                border-radius: 3px;
                background-color: #ffffff;
            }
            QCheckBox::indicator:checked {
                background-color: #4a9eff;
                border-color: #4a9eff;
            }
            QCheckBox::indicator:hover {
                border-color: #999999;
            }

            /* --- FRAMES & SEPARATORS --- */
            #TopFrame, #SearchFrame, #AnnotationToolbar, #DrawingToolbar {
                background-color: #f0f0f0;
                border-bottom: 1px solid #e0e0e0;
            }

            QScrollArea {
                background-color: #f0f0f0;
                border: none;
            }
        """
    widget.setStyleSheet(style_sheet)
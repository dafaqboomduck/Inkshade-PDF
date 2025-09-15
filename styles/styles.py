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

            /* Style for smaller, icon-like buttons */
            QPushButton[objectName="small_button"] {
                background-color: transparent;
                min-width: 30px;
                max-width: 30px;
                min-height: 30px;
                max-height: 30px;
                padding: 0;
                font-size: 16px;
                color: #B5B5C5;
                border: none;
                border-radius: 4px;
            }
            QPushButton[objectName="small_button"]:hover {
                background-color: #3e3e3e;
            }

            /* --- INPUTS AND LABELS --- */
            QLineEdit {
                background-color: #3e3e3e;
                border: 1px solid #555555;
                border-radius: 6px;
                padding: 6px;
                color: #f0f0f0;
            }
            
            QLineEdit[objectName="page_input"], QLineEdit[objectName="zoom_input"] {
                min-width: 60px;
                max-width: 60px;
                text-align: center;
            }
            
            QLabel {
                background-color: transparent;
            }

            /* --- FRAMES & SEPARATORS --- */
            #TopFrame, #SearchFrame {
                background-color: #2e2e2e;
                border-bottom: 2px solid #555555;
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
            
            /* Style for smaller, icon-like buttons */
            QPushButton[objectName="small_button"] {
                background-color: transparent;
                min-width: 30px;
                max-width: 30px;
                min-height: 30px;
                max-height: 30px;
                padding: 0;
                font-size: 16px;
                color: #7A899C;
                border: none;
                border-radius: 4px;
            }
            QPushButton[objectName="small_button"]:hover {
                background-color: #e6e6e6;
            }

            /* --- INPUTS AND LABELS --- */
            QLineEdit {
                background-color: #ffffff;
                border: 1px solid #cccccc;
                border-radius: 6px;
                padding: 6px;
                color: #2e2e2e;
            }
            
            QLineEdit[objectName="page_input"], QLineEdit[objectName="zoom_input"] {
                min-width: 60px;
                max-width: 60px;
                text-align: center;
            }
            
            QLabel {
                background-color: transparent;
            }

            /* --- FRAMES & SEPARATORS --- */
            #TopFrame, #SearchFrame {
                background-color: #f0f0f0;
                border-bottom: 2px solid #cccccc;
            }

            QScrollArea {
                background-color: #f0f0f0;
                border: none;
            }
        """
    widget.setStyleSheet(style_sheet)
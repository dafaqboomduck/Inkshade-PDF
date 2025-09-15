from PyQt5.QtWidgets import QWidget

def apply_style(widget: QWidget, dark_mode: bool):
    """
    Applies a style sheet to the main window and its widgets.
    """
    if dark_mode:
        style_sheet = """
            QMainWindow, QWidget, QLineEdit, QLabel, QFrame {
                background-color: #2e2e2e;
                color: #f0f0f0;
                border: 1px solid #555555;
            }
            
            /* Style for regular buttons */
            QPushButton {
                background-color: #4e4e4e;
                color: #f0f0f0;
                border: 1px solid #777777;
                min-width: 80px;
                min-height: 30px;
            }
            QPushButton:hover {
                background-color: #5a5a5a;
            }

            /* Style for smaller, icon-like buttons */
            QPushButton[objectName="small_button"] {
                min-width: 25px;
                min-height: 25px;
                font-size: 16px;
                padding: 0;
            }

            QScrollArea {
                background-color: #2e2e2e;
                border: none;
            }

            /* Styles for the frames to mimic the separator lines */
            #TopFrame, #SearchFrame {
                background-color: #2e2e2e;
                border: 1px solid #555555;
            }
            
            #TopFrame {
                border-bottom: 1px solid #555555;
            }
            #SearchFrame {
                border-bottom: 1px solid #555555;
            }

            /* Style for specific LineEdits */
            QLineEdit[objectName="page_input"], QLineEdit[objectName="zoom_input"] {
                min-width: 50px;
                max-width: 50px;
                text-align: center;
                border: 1px solid #777777;
                border-radius: 4px;
            }
        """
    else:
        style_sheet = """
            QMainWindow, QWidget, QLineEdit, QLabel, QFrame {
                background-color: #f0f0f0;
                color: #2e2e2e;
                border: 1px solid #cccccc;
            }
            
            /* Style for regular buttons */
            QPushButton {
                background-color: #e0e0e0;
                color: #2e2e2e;
                border: 1px solid #aaaaaa;
                min-width: 80px;
                min-height: 30px;
            }
            QPushButton:hover {
                background-color: #d0d0d0;
            }

            /* Style for smaller, icon-like buttons */
            QPushButton[objectName="small_button"] {
                min-width: 25px;
                min-height: 25px;
                font-size: 16px;
                padding: 0;
            }

            QScrollArea {
                background-color: #f0f0f0;
                border: none;
            }
            
            /* Styles for the frames to mimic the separator lines */
            #TopFrame, #SearchFrame {
                background-color: #f0f0f0;
                border: 1px solid #cccccc;
            }
            
            #TopFrame {
                border-bottom: 1px solid #cccccc;
            }
            #SearchFrame {
                border-bottom: 1px solid #cccccc;
            }

            /* Style for specific LineEdits */
            QLineEdit[objectName="page_input"], QLineEdit[objectName="zoom_input"] {
                min-width: 50px;
                max-width: 50px;
                text-align: center;
                border: 1px solid #aaaaaa;
                border-radius: 4px;
            }
        """
    widget.setStyleSheet(style_sheet)
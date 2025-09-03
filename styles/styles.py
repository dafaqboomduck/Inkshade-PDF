from PyQt5.QtWidgets import QFrame

def apply_style(widget, dark_mode):
    """Apply style sheets based on dark mode."""
    if dark_mode:
        widget.setStyleSheet("background-color: #3B3B3B; color: white;")
        widget.findChild(QFrame, "TopFrame").setStyleSheet("QFrame#TopFrame { background-color: #505050; }")
    else:
        widget.setStyleSheet("background-color: #E8E8E8; color: black;")
        widget.findChild(QFrame, "TopFrame").setStyleSheet("QFrame#TopFrame { background-color: #F0F0F0; }")

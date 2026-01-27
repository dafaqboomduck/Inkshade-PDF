"""
Theme management and styling for the application.
"""
from PyQt5.QtWidgets import QWidget
from typing import Dict, Any
from .models import ThemeColors

class ThemeManager:
    """Manages application themes and styling."""
    
    # Define color schemes
    DARK_THEME = ThemeColors(
        # Backgrounds
        bg_primary="#2e2e2e",
        bg_secondary="#3e3e3e",
        bg_tertiary="#4e4e4e",
        
        # Text
        text_primary="#f0f0f0",
        text_secondary="#B5B5C5",
        text_muted="#8899AA",
        
        # Accent
        accent_primary="#4a9eff",
        accent_hover="#3a8eef",
        accent_active="#2a7edf",
        
        # Borders
        border_primary="#555555",
        border_secondary="#3e3e3e",
        
        # Special
        selection="rgba(255, 255, 0, 100)",
        error="#ff6b6b",
        warning="#ffd43b",
        success="#51cf66"
    )
    
    LIGHT_THEME = ThemeColors(
        # Backgrounds
        bg_primary="#f0f0f0",
        bg_secondary="#ffffff",
        bg_tertiary="#e0e0e0",
        
        # Text
        text_primary="#2e2e2e",
        text_secondary="#7A899C",
        text_muted="#8899AA",
        
        # Accent
        accent_primary="#4a9eff",
        accent_hover="#3a8eef",
        accent_active="#2a7edf",
        
        # Borders
        border_primary="#cccccc",
        border_secondary="#e0e0e0",
        
        # Special
        selection="rgba(0, 89, 195, 100)",
        error="#ff6b6b",
        warning="#ffd43b",
        success="#51cf66"
    )
    
    @classmethod
    def apply_theme(cls, widget: QWidget, dark_mode: bool) -> None:
        """
        Apply theme to a widget and its children.
        
        Args:
            widget: Widget to style
            dark_mode: Whether to use dark theme
        """
        theme = cls.DARK_THEME if dark_mode else cls.LIGHT_THEME
        style_sheet = cls._generate_stylesheet(theme)
        widget.setStyleSheet(style_sheet)
    
    @classmethod
    def _generate_stylesheet(cls, theme: ThemeColors) -> str:
        """
        Generate a complete stylesheet from theme colors.
        
        Args:
            theme: Theme colors to use
            
        Returns:
            Complete CSS stylesheet string
        """
        return f"""
            /* --- GENERAL STYLES --- */
            QMainWindow, QWidget, QLineEdit, QLabel, QFrame {{
                background-color: {theme.bg_primary};
                color: {theme.text_primary};
                border: none;
            }}
            
            /* --- BUTTONS --- */
            QPushButton {{
                background-color: {theme.bg_tertiary};
                color: {theme.text_primary};
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {theme.bg_secondary};
            }}
            QPushButton:pressed {{
                background-color: {theme.bg_primary};
            }}
            QPushButton:disabled {{
                background-color: {theme.bg_secondary};
                color: {theme.text_muted};
            }}
            
            /* --- TOOL BUTTONS --- */
            QToolButton {{
                background-color: transparent;
                color: {theme.text_secondary};
                border: none;
                border-radius: 4px;
                padding: 4px;
            }}
            QToolButton:hover {{
                background-color: {theme.bg_secondary};
            }}
            QToolButton:pressed {{
                background-color: {theme.bg_primary};
            }}
            QToolButton:checked {{
                background-color: {theme.accent_primary};
                color: white;
            }}
            QToolButton:checked:hover {{
                background-color: {theme.accent_hover};
            }}
            
            /* --- INPUTS --- */
            QLineEdit {{
                background-color: {theme.bg_secondary};
                border: 1px solid {theme.border_primary};
                border-radius: 6px;
                padding: 6px 10px;
                color: {theme.text_primary};
            }}
            QLineEdit:focus {{
                border: 1px solid {theme.accent_primary};
            }}
            QLineEdit:disabled {{
                background-color: {theme.bg_primary};
                color: {theme.text_muted};
            }}
            
            QLineEdit[objectName="page_input"], 
            QLineEdit[objectName="zoom_input"] {{
                min-width: 60px;
                max-width: 60px;
                text-align: center;
            }}
            
            /* --- LABELS --- */
            QLabel {{
                background-color: transparent;
            }}
            QLabel[objectName="statusLabel"] {{
                color: {theme.text_muted};
            }}
            
            /* --- SPINBOX --- */
            QSpinBox {{
                background-color: {theme.bg_secondary};
                border: 1px solid {theme.border_primary};
                border-radius: 4px;
                padding: 4px 8px;
                color: {theme.text_primary};
            }}
            QSpinBox:focus {{
                border: 1px solid {theme.accent_primary};
            }}
            QSpinBox::up-button, QSpinBox::down-button {{
                background-color: {theme.bg_tertiary};
                border: none;
                border-radius: 2px;
            }}
            QSpinBox::up-button:hover, QSpinBox::down-button:hover {{
                background-color: {theme.bg_secondary};
            }}
            
            /* --- CHECKBOX --- */
            QCheckBox {{
                color: {theme.text_primary};
                spacing: 6px;
            }}
            QCheckBox::indicator {{
                width: 18px;
                height: 18px;
                border: 2px solid {theme.border_primary};
                border-radius: 3px;
                background-color: {theme.bg_secondary};
            }}
            QCheckBox::indicator:checked {{
                background-color: {theme.accent_primary};
                border-color: {theme.accent_primary};
            }}
            QCheckBox::indicator:hover {{
                border-color: {theme.text_secondary};
            }}
            
            /* --- SCROLL AREA --- */
            QScrollArea {{
                background-color: {theme.bg_primary};
                border: none;
            }}
            
            QScrollBar:vertical {{
                background-color: {theme.bg_primary};
                width: 12px;
                border: none;
            }}
            QScrollBar::handle:vertical {{
                background-color: {theme.bg_tertiary};
                border-radius: 6px;
                min-height: 20px;
            }}
            QScrollBar::handle:vertical:hover {{
                background-color: {theme.bg_secondary};
            }}
            QScrollBar::add-line:vertical, 
            QScrollBar::sub-line:vertical {{
                background: none;
                height: 0px;
            }}
            
            /* --- FRAMES --- */
            #TopFrame {{
                background-color: {theme.bg_primary};
                border-bottom: 1px solid {theme.border_secondary};
            }}
            
            /* --- FLOATING TOOLBARS --- */
            #SearchBar, #AnnotationToolbar, #DrawingToolbar {{
                background-color: {theme.bg_primary};
                border: 1px solid {theme.border_secondary};
                border-radius: 8px;
            }}
            
            /* --- TREE WIDGET (TOC) --- */
            QTreeWidget {{
                background-color: {theme.bg_primary};
                color: {theme.text_primary};
                border: 1px solid {theme.border_secondary};
                border-left: none;
                outline: none;
            }}
            QTreeWidget::item {{
                padding: 4px;
            }}
            QTreeWidget::item:hover {{
                background-color: {theme.bg_secondary};
            }}
            QTreeWidget::item:selected {{
                background-color: {theme.accent_primary};
                color: white;
            }}
            
            /* --- MENU --- */
            QMenu {{
                background-color: {theme.bg_secondary};
                border: 1px solid {theme.border_primary};
                border-radius: 4px;
                padding: 4px;
            }}
            QMenu::item {{
                padding: 6px 20px;
                border-radius: 4px;
            }}
            QMenu::item:selected {{
                background-color: {theme.accent_primary};
                color: white;
            }}
            
            /* --- MESSAGE BOX --- */
            QMessageBox {{
                background-color: {theme.bg_primary};
            }}
            QMessageBox QLabel {{
                color: {theme.text_primary};
            }}
            
            /* --- PROGRESS DIALOG --- */
            QProgressDialog {{
                background-color: {theme.bg_primary};
            }}
            QProgressBar {{
                background-color: {theme.bg_secondary};
                border: 1px solid {theme.border_primary};
                border-radius: 4px;
                text-align: center;
            }}
            QProgressBar::chunk {{
                background-color: {theme.accent_primary};
                border-radius: 3px;
            }}
        """
    
    @classmethod
    def get_theme_colors(cls, dark_mode: bool) -> ThemeColors:
        """
        Get theme colors for the current mode.
        
        Args:
            dark_mode: Whether to get dark theme colors
            
        Returns:
            ThemeColors object
        """
        return cls.DARK_THEME if dark_mode else cls.LIGHT_THEME
    
    @classmethod
    def get_selection_color(cls, dark_mode: bool) -> tuple:
        """
        Get selection highlight color for the current mode.
        
        Args:
            dark_mode: Whether using dark mode
            
        Returns:
            RGBA tuple for selection color
        """
        if dark_mode:
            return (255, 255, 0, 100)  # Yellow for dark mode
        else:
            return (0, 89, 195, 100)  # Blue for light mode


# Convenience function for backwards compatibility
def apply_style(widget: QWidget, dark_mode: bool) -> None:
    """
    Apply theme to a widget (backwards compatibility).
    
    Args:
        widget: Widget to style
        dark_mode: Whether to use dark theme
    """
    ThemeManager.apply_theme(widget, dark_mode)
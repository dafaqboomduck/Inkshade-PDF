"""
Warning manager for handling one-time warnings per session.
"""
from typing import Set, Optional
from enum import Enum
from PyQt5.QtWidgets import QMessageBox, QCheckBox, QWidget


class WarningType(Enum):
    """Types of warnings that can be suppressed."""
    DELETE_ANNOTATION = "delete_annotation"
    UNSAVED_CHANGES = "unsaved_changes"
    CLOSE_PDF_UNSAVED = "close_pdf_unsaved"
    EXIT_UNSAVED = "exit_unsaved"
    OVERWRITE_FILE = "overwrite_file"


class WarningManager:
    """
    Manages warning dialogs to show them only once per session.
    Singleton pattern to maintain state across the application.
    """
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._initialized = True
        self._suppressed_warnings: Set[WarningType] = set()
        self._session_preferences = {
            "remember_choice": False,
            "last_choices": {}
        }
    
    def should_show_warning(self, warning_type: WarningType) -> bool:
        """
        Check if a warning should be shown.
        
        Args:
            warning_type: Type of warning to check
            
        Returns:
            True if warning should be shown, False if suppressed
        """
        return warning_type not in self._suppressed_warnings
    
    def suppress_warning(self, warning_type: WarningType) -> None:
        """
        Suppress a warning for the rest of the session.
        
        Args:
            warning_type: Type of warning to suppress
        """
        self._suppressed_warnings.add(warning_type)
    
    def reset_warning(self, warning_type: WarningType) -> None:
        """
        Reset a warning so it will show again.
        
        Args:
            warning_type: Type of warning to reset
        """
        self._suppressed_warnings.discard(warning_type)
    
    def reset_all_warnings(self) -> None:
        """Reset all warnings for the session."""
        self._suppressed_warnings.clear()
        self._session_preferences["last_choices"].clear()
    
    def get_last_choice(self, warning_type: WarningType) -> Optional[int]:
        """
        Get the last choice made for a warning type.
        
        Args:
            warning_type: Type of warning
            
        Returns:
            Last QMessageBox result or None
        """
        return self._session_preferences["last_choices"].get(warning_type)
    
    def show_warning(self, parent: QWidget, warning_type: WarningType,
                    title: str, message: str, 
                    buttons: int = QMessageBox.Yes | QMessageBox.No,
                    default_button: int = QMessageBox.No,
                    show_dont_ask: bool = True) -> int:
        """
        Show a warning dialog with optional "don't ask again" checkbox.
        
        Args:
            parent: Parent widget
            warning_type: Type of warning
            title: Dialog title
            message: Warning message
            buttons: QMessageBox button flags
            default_button: Default button
            show_dont_ask: Whether to show "don't ask again" checkbox
            
        Returns:
            QMessageBox result
        """
        # Check if warning is suppressed
        if not self.should_show_warning(warning_type):
            # Return the last choice made for this warning type
            last_choice = self.get_last_choice(warning_type)
            if last_choice is not None:
                return last_choice
            # Default to Yes if we're suppressing but have no previous choice
            return QMessageBox.Yes
        
        # Create message box
        msg_box = QMessageBox(parent)
        msg_box.setIcon(QMessageBox.Question)
        msg_box.setWindowTitle(title)
        msg_box.setText(message)
        msg_box.setStandardButtons(buttons)
        msg_box.setDefaultButton(default_button)
        
        # Add "Don't ask again" checkbox if requested
        dont_ask_checkbox = None
        if show_dont_ask:
            dont_ask_checkbox = QCheckBox("Don't ask again this session")
            msg_box.setCheckBox(dont_ask_checkbox)
        
        # Show dialog and get result
        result = msg_box.exec_()
        
        # Store the choice
        self._session_preferences["last_choices"][warning_type] = result
        
        # Check if user wants to suppress future warnings
        if dont_ask_checkbox and dont_ask_checkbox.isChecked():
            self.suppress_warning(warning_type)
        
        return result
    
    def show_confirmation(self, parent: QWidget, warning_type: WarningType,
                         title: str, message: str,
                         show_dont_ask: bool = True) -> bool:
        """
        Show a simple Yes/No confirmation dialog.
        
        Args:
            parent: Parent widget
            warning_type: Type of warning
            title: Dialog title
            message: Confirmation message
            show_dont_ask: Whether to show "don't ask again" checkbox
            
        Returns:
            True if user clicked Yes, False otherwise
        """
        result = self.show_warning(
            parent, warning_type, title, message,
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
            show_dont_ask
        )
        return result == QMessageBox.Yes
    
    def show_save_discard_cancel(self, parent: QWidget, 
                                 warning_type: WarningType,
                                 title: str = "Unsaved Changes",
                                 message: str = "You have unsaved changes. Do you want to save them?",
                                 show_dont_ask: bool = False) -> int:
        """
        Show a Save/Discard/Cancel dialog for unsaved changes.
        
        Args:
            parent: Parent widget
            warning_type: Type of warning
            title: Dialog title
            message: Warning message
            show_dont_ask: Whether to show "don't ask again" checkbox
            
        Returns:
            QMessageBox.Save, QMessageBox.Discard, or QMessageBox.Cancel
        """
        # For save/discard/cancel, we typically don't want to suppress
        # But we'll allow it if specifically requested
        return self.show_warning(
            parent, warning_type, title, message,
            QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
            QMessageBox.Save,
            show_dont_ask
        )


# Global instance for easy access
warning_manager = WarningManager()
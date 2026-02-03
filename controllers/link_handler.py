"""
Handles link click actions and navigation.
"""

import webbrowser
from typing import TYPE_CHECKING

from PyQt5.QtCore import QObject, pyqtSignal
from PyQt5.QtWidgets import QMessageBox

from core.page.link_layer import LinkInfo, LinkType

if TYPE_CHECKING:
    from ui.windows.main_window import MainWindow


class LinkNavigationHandler(QObject):
    """
    Handles all link-related navigation and actions.

    Supports:
    - Internal page navigation
    - External URL opening (with security confirmation)
    - Named destination resolution
    - File launch handling
    """

    # Signals
    navigation_requested = pyqtSignal(int, float)  # page_num (1-based), y_offset
    external_link_opened = pyqtSignal(str)  # URL
    link_action_failed = pyqtSignal(str)  # error message

    def __init__(self, main_window: "MainWindow" = None, parent=None):
        super().__init__(parent)
        self.main_window = main_window

        # Security settings
        self.confirm_external_links = True
        self.allowed_protocols = {"http", "https", "mailto", "tel"}
        self.allow_file_launch = False

    def handle_link_click(self, link: LinkInfo) -> bool:
        """
        Process a clicked link.

        Args:
            link: The LinkInfo object that was clicked

        Returns:
            True if the link was handled successfully
        """
        if link.link_type == LinkType.GOTO:
            return self._navigate_to_internal(link)

        elif link.link_type == LinkType.GOTO_R:
            return self._navigate_to_remote(link)

        elif link.link_type == LinkType.URI:
            return self._open_external_url(link)

        elif link.link_type == LinkType.NAMED:
            return self._navigate_to_named(link)

        elif link.link_type == LinkType.LAUNCH:
            return self._handle_launch(link)

        return False

    def _navigate_to_internal(self, link: LinkInfo) -> bool:
        """Navigate to an internal page destination."""

        if not link.destination:
            self.link_action_failed.emit("Invalid link destination")
            return False

        dest = link.destination
        page_num = dest.page_num + 1  # Convert to 1-based
        y_offset = dest.y if dest.y else 0.0

        # Emit signal for navigation
        self.navigation_requested.emit(page_num, y_offset)

        # Direct navigation if main_window available
        if self.main_window:
            self.main_window.page_manager.jump_to_page(page_num, y_offset)
        else:
            print("DEBUG: main_window is None!")
        return True

    def _navigate_to_remote(self, link: LinkInfo) -> bool:
        """Handle links to external PDF files."""
        if not link.file_path:
            self.link_action_failed.emit("No file path specified")
            return False

        # Security: Don't automatically open external files
        if self.main_window:
            reply = QMessageBox.question(
                self.main_window,
                "Open External PDF",
                f"This link points to an external file:\n{link.file_path}\n\n"
                "Do you want to open it?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )

            if reply == QMessageBox.Yes:
                # Try to open the file
                import os

                if os.path.exists(link.file_path):
                    self.main_window.load_pdf(link.file_path)

                    # Navigate to destination if specified
                    if link.destination:
                        self._navigate_to_internal(link)
                    return True
                else:
                    self.link_action_failed.emit(f"File not found: {link.file_path}")

        return False

    def _open_external_url(self, link: LinkInfo) -> bool:
        """Open an external URL in the system browser."""
        url = link.uri
        if not url:
            self.link_action_failed.emit("No URL specified")
            return False

        # Security check: validate URL protocol
        protocol = self._get_url_protocol(url)
        if protocol not in self.allowed_protocols:
            self.link_action_failed.emit(f"URL protocol '{protocol}' is not allowed")
            return False

        # Confirm with user if enabled
        if self.confirm_external_links and self.main_window:
            # Truncate long URLs for display
            display_url = url if len(url) <= 80 else url[:77] + "..."

            reply = QMessageBox.question(
                self.main_window,
                "Open External Link",
                f"Open this link in your browser?\n\n{display_url}",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )

            if reply != QMessageBox.Yes:
                return False

        # Open the URL
        try:
            webbrowser.open(url)
            self.external_link_opened.emit(url)
            return True
        except Exception as e:
            self.link_action_failed.emit(f"Failed to open URL: {e}")
            return False

    def _navigate_to_named(self, link: LinkInfo) -> bool:
        """Navigate to a named destination."""
        # If destination was resolved during extraction, use it
        if link.destination:
            return self._navigate_to_internal(link)

        # Try to resolve at navigation time
        if not link.named_dest:
            self.link_action_failed.emit("No destination name specified")
            return False

        if self.main_window and self.main_window.pdf_reader.doc:
            doc = self.main_window.pdf_reader.doc
            try:
                dest = doc.resolve_link(f"#{link.named_dest}")
                if dest and isinstance(dest, dict):
                    page_num = dest.get("page", 0) + 1
                    to_point = dest.get("to")
                    y_offset = getattr(to_point, "y", 0) if to_point else 0

                    self.navigation_requested.emit(page_num, y_offset)
                    self.main_window.page_manager.jump_to_page(page_num, y_offset)
                    return True
            except Exception as e:
                self.link_action_failed.emit(f"Failed to resolve destination: {e}")

        return False

    def _handle_launch(self, link: LinkInfo) -> bool:
        """Handle launch links (opening external applications)."""
        if not self.allow_file_launch:
            if self.main_window:
                QMessageBox.warning(
                    self.main_window,
                    "Action Blocked",
                    "Opening external applications is disabled for security.\n\n"
                    f"Target: {link.file_path or 'Unknown'}",
                )
            return False

        # Even if allowed, require confirmation
        if self.main_window and link.file_path:
            reply = QMessageBox.warning(
                self.main_window,
                "Launch Application",
                f"This link wants to open an external application:\n\n"
                f"{link.file_path}\n\n"
                "This could be dangerous. Continue?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )

            if reply == QMessageBox.Yes:
                import os
                import subprocess

                try:
                    if os.name == "nt":  # Windows
                        os.startfile(link.file_path)
                    elif os.name == "posix":  # macOS/Linux
                        subprocess.call(["xdg-open", link.file_path])
                    return True
                except Exception as e:
                    self.link_action_failed.emit(f"Failed to launch: {e}")

        return False

    def _get_url_protocol(self, url: str) -> str:
        """Extract protocol from URL."""
        if "://" in url:
            return url.split("://")[0].lower()
        elif url.startswith("mailto:"):
            return "mailto"
        elif url.startswith("tel:"):
            return "tel"
        return "unknown"

    def get_link_tooltip(self, link: LinkInfo) -> str:
        """Generate a tooltip string for a link."""
        if link.link_type == LinkType.URI:
            url = link.uri or ""
            if len(url) > 60:
                return url[:57] + "..."
            return url

        elif link.link_type == LinkType.GOTO:
            if link.destination:
                return f"Go to page {link.destination.page_num + 1}"
            return "Internal link"

        elif link.link_type == LinkType.NAMED:
            return f"Go to: {link.named_dest or 'bookmark'}"

        elif link.link_type == LinkType.LAUNCH:
            return f"Open: {link.file_path or 'application'}"

        return "Link"

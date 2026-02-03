"""
Character-level text selection management.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

from PyQt5.QtCore import QObject, pyqtSignal

from core.page.page_model import PageModel
from core.page.text_layer import CharacterInfo


@dataclass
class SelectionAnchor:
    """Represents a selection anchor point."""

    page_index: int
    character: CharacterInfo

    def __hash__(self):
        return hash((self.page_index, self.character.global_index))

    def __eq__(self, other):
        if not isinstance(other, SelectionAnchor):
            return False
        return (
            self.page_index == other.page_index
            and self.character.global_index == other.character.global_index
        )


@dataclass
class PageSelection:
    """Selection state for a single page."""

    characters: List[CharacterInfo] = field(default_factory=list)
    rects: List[Tuple[float, float, float, float]] = field(default_factory=list)

    @property
    def text(self) -> str:
        """Get selected text for this page."""
        if not self.characters:
            return ""

        # Group by line
        lines = {}
        for char in self.characters:
            key = (char.block_index, char.line_index)
            if key not in lines:
                lines[key] = []
            lines[key].append(char)

        # Build text with line breaks
        result = []
        for key in sorted(lines.keys()):
            line_chars = sorted(lines[key], key=lambda c: c.global_index)
            result.append("".join(c.char for c in line_chars))

        return "\n".join(result)


class SelectionManager(QObject):
    """
    Manages text selection state across multiple pages.

    Supports:
    - Character-level selection precision
    - Multi-page selection
    - Selection extension with modifiers
    - Selection rect generation for painting
    """

    # Signals
    selection_changed = pyqtSignal()
    selection_cleared = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)

        # Selection state
        self.anchor: Optional[SelectionAnchor] = None  # Start of selection
        self.focus: Optional[SelectionAnchor] = None  # Current end of selection

        # Computed selection per page
        self._page_selections: Dict[int, PageSelection] = {}

        # Page models reference (set by parent)
        self._page_models: Dict[int, PageModel] = {}

        # Selection mode
        self.is_selecting: bool = False

    def set_page_models(self, models: Dict[int, PageModel]):
        """Set reference to page models for selection computation."""
        self._page_models = models

    def start_selection(self, page_index: int, character: CharacterInfo):
        """
        Begin a new selection at the specified character.

        Args:
            page_index: Page where selection starts
            character: Character to start selection at
        """
        self.clear()

        self.anchor = SelectionAnchor(page_index, character)
        self.focus = SelectionAnchor(page_index, character)
        self.is_selecting = True

        self._update_selection()
        self.selection_changed.emit()

    def extend_selection(self, page_index: int, character: CharacterInfo):
        """
        Extend selection to the specified character.

        Args:
            page_index: Page where selection extends to
            character: Character to extend selection to
        """
        if self.anchor is None:
            return

        self.focus = SelectionAnchor(page_index, character)
        self._update_selection()
        self.selection_changed.emit()

    def finish_selection(self):
        """Complete the current selection operation."""
        self.is_selecting = False

    def _update_selection(self):
        """Recalculate selected characters based on anchor and focus."""
        self._page_selections.clear()

        if self.anchor is None or self.focus is None:
            return

        # Determine selection direction
        start = self.anchor
        end = self.focus

        # Normalize: start should come before end
        if start.page_index > end.page_index:
            start, end = end, start
        elif (
            start.page_index == end.page_index
            and start.character.global_index > end.character.global_index
        ):
            start, end = end, start

        # Single page selection
        if start.page_index == end.page_index:
            page_model = self._page_models.get(start.page_index)
            if page_model:
                chars = page_model.text_layer.get_chars_in_range(
                    start.character, end.character
                )
                rects = page_model.text_layer.get_selection_rects(chars)
                self._page_selections[start.page_index] = PageSelection(
                    characters=chars, rects=rects
                )
        else:
            # Multi-page selection
            for page_idx in range(start.page_index, end.page_index + 1):
                page_model = self._page_models.get(page_idx)
                if not page_model:
                    continue

                text_layer = page_model.text_layer

                if page_idx == start.page_index:
                    # First page: from start char to end of page
                    if text_layer.characters:
                        chars = text_layer.get_chars_in_range(
                            start.character, text_layer.characters[-1]
                        )
                        rects = text_layer.get_selection_rects(chars)
                        self._page_selections[page_idx] = PageSelection(
                            characters=chars, rects=rects
                        )

                elif page_idx == end.page_index:
                    # Last page: from start of page to end char
                    if text_layer.characters:
                        chars = text_layer.get_chars_in_range(
                            text_layer.characters[0], end.character
                        )
                        rects = text_layer.get_selection_rects(chars)
                        self._page_selections[page_idx] = PageSelection(
                            characters=chars, rects=rects
                        )

                else:
                    # Middle page: entire page selected
                    chars = text_layer.characters.copy()
                    rects = text_layer.get_selection_rects(chars)
                    self._page_selections[page_idx] = PageSelection(
                        characters=chars, rects=rects
                    )

    def get_selection_for_page(self, page_index: int) -> Optional[PageSelection]:
        """Get selection data for a specific page."""
        return self._page_selections.get(page_index)

    def get_selection_rects(
        self, page_index: int
    ) -> List[Tuple[float, float, float, float]]:
        """Get selection rectangles for a page (for painting)."""
        selection = self._page_selections.get(page_index)
        return selection.rects if selection else []

    def get_selected_text(self) -> str:
        """Get all selected text across all pages."""
        if not self._page_selections:
            return ""

        pages = []
        for page_idx in sorted(self._page_selections.keys()):
            selection = self._page_selections[page_idx]
            if selection.text:
                pages.append(selection.text)

        return "\n\n".join(pages)  # Double newline between pages

    def has_selection(self) -> bool:
        """Check if there is any selection."""
        return bool(self._page_selections)

    def get_selected_pages(self) -> List[int]:
        """Get list of pages with selection."""
        return list(self._page_selections.keys())

    def clear(self):
        """Clear all selection state."""
        had_selection = self.has_selection()

        self.anchor = None
        self.focus = None
        self.is_selecting = False
        self._page_selections.clear()

        if had_selection:
            self.selection_cleared.emit()

    def select_word_at(self, page_index: int, character: CharacterInfo):
        """
        Select the entire word containing the character.

        Useful for double-click to select word.
        """
        page_model = self._page_models.get(page_index)
        if not page_model:
            return

        text_layer = page_model.text_layer
        chars = text_layer.characters

        if not chars or character not in chars:
            return

        idx = character.global_index

        # Find word boundaries
        start_idx = idx
        end_idx = idx

        # Expand backward
        while start_idx > 0:
            prev_char = chars[start_idx - 1]
            if prev_char.char.isspace() or prev_char.line_index != character.line_index:
                break
            start_idx -= 1

        # Expand forward
        while end_idx < len(chars) - 1:
            next_char = chars[end_idx + 1]
            if next_char.char.isspace() or next_char.line_index != character.line_index:
                break
            end_idx += 1

        # Set selection
        self.anchor = SelectionAnchor(page_index, chars[start_idx])
        self.focus = SelectionAnchor(page_index, chars[end_idx])
        self._update_selection()
        self.selection_changed.emit()

    def select_line_at(self, page_index: int, character: CharacterInfo):
        """
        Select the entire line containing the character.

        Useful for triple-click to select line.
        """
        page_model = self._page_models.get(page_index)
        if not page_model:
            return

        text_layer = page_model.text_layer

        # Find all characters on the same line
        line_chars = [
            c
            for c in text_layer.characters
            if c.block_index == character.block_index
            and c.line_index == character.line_index
        ]

        if not line_chars:
            return

        line_chars.sort(key=lambda c: c.global_index)

        self.anchor = SelectionAnchor(page_index, line_chars[0])
        self.focus = SelectionAnchor(page_index, line_chars[-1])
        self._update_selection()
        self.selection_changed.emit()

    def select_all(self, page_index: int):
        """Select all text on a page."""
        page_model = self._page_models.get(page_index)
        if not page_model or not page_model.text_layer.characters:
            return

        chars = page_model.text_layer.characters
        self.anchor = SelectionAnchor(page_index, chars[0])
        self.focus = SelectionAnchor(page_index, chars[-1])
        self._update_selection()
        self.selection_changed.emit()

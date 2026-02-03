from dataclasses import dataclass, field
from typing import List, Tuple

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

"""
Data models for the reading script and prosody system.
"""

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import List, Optional

from core.page.models import CharacterInfo
from narration.layout.models import LayoutLabel


class TextRole(Enum):
    """
    Semantic role of a text segment for narration.

    Multiple LayoutLabels can map to the same TextRole (e.g. both
    PAGE_HEADER and PAGE_FOOTER → SKIP).
    """

    TITLE = auto()
    SECTION_HEADER = auto()
    BODY = auto()
    LIST_ITEM = auto()
    CAPTION = auto()
    FOOTNOTE = auto()
    FORMULA = auto()
    PAGE_TRANSITION = auto()  # synthetic pause inserted between pages
    SKIP = auto()  # page headers, footers, pictures, tables


# LayoutLabel → TextRole mapping
LABEL_TO_ROLE = {
    LayoutLabel.TITLE: TextRole.TITLE,
    LayoutLabel.SECTION_HEADER: TextRole.SECTION_HEADER,
    LayoutLabel.TEXT: TextRole.BODY,
    LayoutLabel.LIST_ITEM: TextRole.LIST_ITEM,
    LayoutLabel.CAPTION: TextRole.CAPTION,
    LayoutLabel.FOOTNOTE: TextRole.FOOTNOTE,
    LayoutLabel.FORMULA: TextRole.FORMULA,
    LayoutLabel.PAGE_HEADER: TextRole.SKIP,
    LayoutLabel.PAGE_FOOTER: TextRole.SKIP,
    LayoutLabel.PICTURE: TextRole.SKIP,
    LayoutLabel.TABLE: TextRole.SKIP,
    LayoutLabel.UNKNOWN: TextRole.BODY,  # safe default
}


@dataclass
class ProsodyRule:
    """
    Prosody parameters for a text segment based on its role.

    Durations in seconds.  Speed is a multiplier (1.0 = normal,
    0.85 = slower / more deliberate, 1.1 = faster).
    """

    pause_before: float = 0.0
    pause_after: float = 0.0
    speed_factor: float = 1.0
    skip: bool = False


@dataclass
class ReadingInstruction:
    """
    A single unit in the reading script — one thing to speak or skip.

    For BODY text the script builder splits blocks into sentences, so
    each instruction is typically one sentence.  Titles and headings
    stay as a single instruction.
    """

    text: str
    role: TextRole
    prosody: ProsodyRule
    page_index: int
    block_index: int

    # Character references for future highlighting integration
    characters: List[CharacterInfo] = field(default_factory=list)

    @property
    def should_skip(self) -> bool:
        return self.prosody.skip

    def __repr__(self) -> str:
        preview = self.text[:60].replace("\n", " ")
        if self.should_skip:
            return f"ReadingInstruction(SKIP, '{preview}')"
        return (
            f"ReadingInstruction({self.role.name}, "
            f"speed={self.prosody.speed_factor}x, "
            f"pause=[{self.prosody.pause_before}s|{self.prosody.pause_after}s], "
            f"'{preview}')"
        )

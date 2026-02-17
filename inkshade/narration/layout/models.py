"""
Data models for document layout detection and block classification.

``LayoutLabel`` corresponds to the 11 DocLayNet classes produced by the
YOLO detector.  ``ClassifiedBlock`` pairs a text ``BlockInfo`` with its
resolved label and confidence score.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional, Tuple

from core.page.models import BlockInfo


class LayoutLabel(Enum):
    """Document layout element types (DocLayNet taxonomy)."""

    CAPTION = 0
    FOOTNOTE = 1
    FORMULA = 2
    LIST_ITEM = 3
    PAGE_FOOTER = 4
    PAGE_HEADER = 5
    PICTURE = 6
    SECTION_HEADER = 7
    TABLE = 8
    TEXT = 9
    TITLE = 10
    UNKNOWN = -1


DOCLAYNET_INDEX_TO_LABEL = {
    label.value: label for label in LayoutLabel if label.value >= 0
}
"""Reverse lookup: YOLO class index → ``LayoutLabel``."""


@dataclass
class LayoutRegion:
    """
    A region detected by the YOLO layout model.

    Coordinates are in **pixel space** of the rendered page image
    (dependent on the render scale).
    """

    label: LayoutLabel
    confidence: float
    bbox: Tuple[float, float, float, float]

    @property
    def area(self) -> float:
        x0, y0, x1, y1 = self.bbox
        return max(0, x1 - x0) * max(0, y1 - y0)

    @property
    def center(self) -> Tuple[float, float]:
        x0, y0, x1, y1 = self.bbox
        return ((x0 + x1) / 2, (y0 + y1) / 2)

    def to_pdf_coords(self, scale: float) -> "LayoutRegion":
        """Return a copy with bbox converted to PDF point space."""
        x0, y0, x1, y1 = self.bbox
        return LayoutRegion(
            label=self.label,
            confidence=self.confidence,
            bbox=(x0 / scale, y0 / scale, x1 / scale, y1 / scale),
        )

    def __repr__(self) -> str:
        x0, y0, x1, y1 = self.bbox
        return (
            f"LayoutRegion({self.label.name}, "
            f"conf={self.confidence:.2f}, "
            f"bbox=[{x0:.0f},{y0:.0f},{x1:.0f},{y1:.0f}])"
        )


@dataclass
class ClassifiedBlock:
    """
    A text block paired with its resolved layout classification.

    Primary data structure consumed by the reading script builder.
    """

    block: BlockInfo
    label: LayoutLabel
    confidence: float
    source_region: Optional[LayoutRegion] = None
    refined: bool = False

    @property
    def text(self) -> str:
        return self.block.text

    @property
    def bbox(self) -> Tuple[float, float, float, float]:
        return self.block.bbox

    def __repr__(self) -> str:
        preview = self.text[:50].replace("\n", " ")
        tag = " [refined]" if self.refined else ""
        return (
            f"ClassifiedBlock({self.label.name}, "
            f"conf={self.confidence:.2f}{tag}, "
            f"'{preview}')"
        )

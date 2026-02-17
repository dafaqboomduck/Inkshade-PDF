"""
Refines layout classifications using typographic and positional features.

Handles two cases:

1. **UNKNOWN blocks** (no YOLO match) — classified from scratch using
   font size, weight, position, and word count.
2. **Low-confidence detections** — cross-checked against text features
   and overridden when the evidence disagrees.
"""

import re
from typing import Dict, List, Optional, Tuple

from core.page.models import BlockInfo

from .models import ClassifiedBlock, LayoutLabel

_RE_PAGE_NUMBER = re.compile(r"^\s*[-–—]?\s*\d{1,4}\s*[-–—]?\s*$")
_RE_BULLET = re.compile(
    r"^\s*(?:[•●○◦▪▸►–—-]|\d{1,3}[.)]\s|[a-zA-Z][.)]\s|[ivxIVX]+[.)]\s)"
)


class PageStats:
    """Aggregate typographic statistics for a single page."""

    def __init__(self, blocks: List[BlockInfo], page_width: float, page_height: float):
        self.page_width = page_width
        self.page_height = page_height

        all_sizes: List[float] = []
        for b in blocks:
            all_sizes.extend(b.all_font_sizes)

        self.median_font_size = self._median(all_sizes) if all_sizes else 12.0
        self.max_font_size = max(all_sizes) if all_sizes else 12.0
        self.min_font_size = min(all_sizes) if all_sizes else 12.0

    @staticmethod
    def _median(values: List[float]) -> float:
        s = sorted(values)
        mid = len(s) // 2
        if len(s) % 2 == 0:
            return (s[mid - 1] + s[mid]) / 2
        return s[mid]


def _classify_by_features(
    block: BlockInfo,
    stats: PageStats,
) -> Tuple[LayoutLabel, float]:
    """
    Classify a block using typographic and positional heuristics.

    Returns:
        ``(label, confidence)`` where confidence is in ``[0, 1]``.
    """
    text = block.text.strip()
    font_size = block.dominant_font_size
    ratio = font_size / stats.median_font_size if stats.median_font_size else 1.0
    bold = block.is_bold
    word_count = block.word_count
    y_center = (block.bbox[1] + block.bbox[3]) / 2
    y_ratio = y_center / stats.page_height if stats.page_height else 0.5

    if _RE_PAGE_NUMBER.match(text):
        if y_ratio < 0.08 or y_ratio > 0.92:
            return LayoutLabel.PAGE_FOOTER, 0.85
        return LayoutLabel.TEXT, 0.3

    if y_ratio < 0.06 and word_count <= 15:
        return LayoutLabel.PAGE_HEADER, 0.7
    if y_ratio > 0.94 and word_count <= 15:
        return LayoutLabel.PAGE_FOOTER, 0.7

    if ratio >= 1.6 and bold and word_count <= 20 and y_ratio < 0.4:
        return LayoutLabel.TITLE, 0.75

    if ratio >= 1.2 and word_count <= 20:
        return LayoutLabel.SECTION_HEADER, 0.7
    if bold and word_count <= 15 and ratio >= 1.0:
        return LayoutLabel.SECTION_HEADER, 0.6

    lines = text.split("\n")
    bullet_lines = sum(1 for ln in lines if _RE_BULLET.match(ln))
    if bullet_lines > 0 and bullet_lines >= len(lines) * 0.5:
        return LayoutLabel.LIST_ITEM, 0.65

    if ratio <= 0.85 and y_ratio > 0.75:
        return LayoutLabel.FOOTNOTE, 0.6

    if ratio <= 0.9 and word_count <= 30 and 0.1 < y_ratio < 0.9:
        return LayoutLabel.CAPTION, 0.4

    return LayoutLabel.TEXT, 0.5


def _should_override(
    cb: ClassifiedBlock,
    stats: PageStats,
) -> Optional[Tuple[LayoutLabel, float]]:
    """
    Cross-check a YOLO classification against text features.

    Returns:
        ``(new_label, new_confidence)`` if an override is warranted,
        ``None`` to keep the original.
    """
    block = cb.block
    text = block.text.strip()
    font_size = block.dominant_font_size
    ratio = font_size / stats.median_font_size if stats.median_font_size else 1.0
    bold = block.is_bold
    word_count = block.word_count
    y_center = (block.bbox[1] + block.bbox[3]) / 2
    y_ratio = y_center / stats.page_height if stats.page_height else 0.5

    if cb.confidence > 0.75:
        return None

    if cb.label == LayoutLabel.SECTION_HEADER:
        if y_ratio < 0.08:
            return LayoutLabel.PAGE_HEADER, 0.85
        if y_ratio > 0.92:
            return LayoutLabel.PAGE_FOOTER, 0.85

    if cb.label == LayoutLabel.TEXT:
        if ratio >= 1.5 and bold and word_count <= 15:
            return LayoutLabel.SECTION_HEADER, 0.65
        if ratio >= 1.8 and word_count <= 20 and y_ratio < 0.35:
            return LayoutLabel.TITLE, 0.6

    if cb.label == LayoutLabel.TITLE:
        if y_ratio < 0.08 and word_count <= 15:
            return LayoutLabel.PAGE_HEADER, 0.85
        if y_ratio > 0.92 and word_count <= 15:
            return LayoutLabel.PAGE_FOOTER, 0.85

    if cb.label == LayoutLabel.SECTION_HEADER:
        if word_count > 40 and ratio < 1.15:
            return LayoutLabel.TEXT, 0.6

    if cb.label == LayoutLabel.TEXT and _RE_PAGE_NUMBER.match(text):
        if y_ratio < 0.08 or y_ratio > 0.92:
            return LayoutLabel.PAGE_FOOTER, 0.8

    if cb.label == LayoutLabel.TEXT:
        lines = text.split("\n")
        bullet_lines = sum(1 for ln in lines if _RE_BULLET.match(ln))
        if bullet_lines >= len(lines) * 0.6 and len(lines) >= 2:
            return LayoutLabel.LIST_ITEM, 0.6

    return None


def refine_classifications(
    classified_blocks: List[ClassifiedBlock],
    page_width: float,
    page_height: float,
) -> List[ClassifiedBlock]:
    """
    Refine layout classifications in place using typographic features.

    UNKNOWN blocks are classified from scratch.  Low-confidence
    detections are cross-checked and potentially overridden.
    """
    raw_blocks = [cb.block for cb in classified_blocks]
    stats = PageStats(raw_blocks, page_width, page_height)

    for cb in classified_blocks:
        if cb.label == LayoutLabel.UNKNOWN:
            label, conf = _classify_by_features(cb.block, stats)
            cb.label = label
            cb.confidence = conf
            cb.refined = True
            continue

        override = _should_override(cb, stats)
        if override is not None:
            cb.label, cb.confidence = override
            cb.refined = True

    return classified_blocks


def detect_running_headers_footers(
    pages_classified: Dict[int, List[ClassifiedBlock]],
    page_heights: Dict[int, float],
    min_occurrences: int = 3,
) -> Dict[int, List[ClassifiedBlock]]:
    """
    Detect repeated text at consistent positions across pages and
    reclassify as ``PAGE_HEADER`` / ``PAGE_FOOTER``.

    A text string appearing in the top or bottom 8% of the page on
    *min_occurrences* or more consecutive pages is reclassified.
    Modifies blocks in place.
    """
    candidates: Dict[Tuple[str, str], List[Tuple[int, ClassifiedBlock]]] = {}

    for page_idx, blocks in sorted(pages_classified.items()):
        h = page_heights.get(page_idx, 792.0)
        for cb in blocks:
            y_center = (cb.bbox[1] + cb.bbox[3]) / 2
            y_ratio = y_center / h if h else 0.5

            if y_ratio < 0.08:
                pos = "top"
            elif y_ratio > 0.92:
                pos = "bottom"
            else:
                continue

            norm = cb.text.strip().lower()
            if len(norm) < 3:
                continue

            key = (norm, pos)
            if key not in candidates:
                candidates[key] = []
            candidates[key].append((page_idx, cb))

    for (_, pos), occurrences in candidates.items():
        if len(occurrences) < min_occurrences:
            continue

        pages_with = sorted(set(p for p, _ in occurrences))
        run_len = 1
        max_run = 1
        for i in range(1, len(pages_with)):
            if pages_with[i] == pages_with[i - 1] + 1:
                run_len += 1
                max_run = max(max_run, run_len)
            else:
                run_len = 1

        if max_run >= min_occurrences:
            new_label = (
                LayoutLabel.PAGE_HEADER if pos == "top" else LayoutLabel.PAGE_FOOTER
            )
            for _, cb in occurrences:
                cb.label = new_label
                cb.confidence = 0.9
                cb.refined = True

    return pages_classified

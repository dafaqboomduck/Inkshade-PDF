"""
Character-level text extraction and selection for PDF pages.
"""

from typing import Dict, List, Optional, Tuple

import fitz

from .models import BlockInfo, CharacterInfo, LineInfo, SpanInfo


class PageTextLayer:
    """
    Manages character-level text data for a PDF page.

    Provides efficient character lookup and selection operations.
    """

    def __init__(self, page: fitz.Page):
        self.page = page
        self.blocks: List[BlockInfo] = []
        self.characters: List[CharacterInfo] = []
        self._char_grid: Dict[Tuple[int, int], List[CharacterInfo]] = {}
        self._grid_size = 50  # Grid cell size for spatial lookup

        self._extract_text_structure()
        self._build_spatial_index()

    def _extract_text_structure(self):
        """Extract character-level text structure from the page."""
        # Use rawdict for character-level access with positions
        flags = (
            fitz.TEXT_PRESERVE_WHITESPACE
            | fitz.TEXT_PRESERVE_LIGATURES
            | fitz.TEXT_PRESERVE_IMAGES
        )

        try:
            text_dict = self.page.get_text("rawdict", flags=flags)
        except Exception as e:
            print(f"Failed to extract text: {e}")
            return

        char_index = 0

        for block_idx, block_data in enumerate(text_dict.get("blocks", [])):
            # Skip image blocks
            if block_data.get("type") != 0:
                continue

            block = BlockInfo(
                bbox=tuple(block_data.get("bbox", (0, 0, 0, 0))), block_type=0
            )

            for line_idx, line_data in enumerate(block_data.get("lines", [])):
                line = LineInfo(
                    bbox=tuple(line_data.get("bbox", (0, 0, 0, 0))),
                    wmode=line_data.get("wmode", 0),
                    dir_vector=tuple(line_data.get("dir", (1, 0))),
                )

                for span_idx, span_data in enumerate(line_data.get("spans", [])):
                    span = SpanInfo(
                        font_name=span_data.get("font", ""),
                        font_size=span_data.get("size", 12.0),
                        color=span_data.get("color", 0),
                        flags=span_data.get("flags", 0),
                        bbox=tuple(span_data.get("bbox", (0, 0, 0, 0))),
                    )

                    # Extract individual characters
                    for char_data in span_data.get("chars", []):
                        char = CharacterInfo(
                            char=char_data.get("c", ""),
                            bbox=tuple(char_data.get("bbox", (0, 0, 0, 0))),
                            origin=tuple(char_data.get("origin", (0, 0))),
                            span_index=span_idx,
                            line_index=line_idx,
                            block_index=block_idx,
                            font_name=span.font_name,
                            font_size=span.font_size,
                            color=span.color,
                            global_index=char_index,
                        )

                        span.characters.append(char)
                        self.characters.append(char)
                        char_index += 1

                    if span.characters:
                        line.spans.append(span)

                if line.spans:
                    block.lines.append(line)

            if block.lines:
                self.blocks.append(block)

    def _build_spatial_index(self):
        """Build a grid-based spatial index for fast character lookup."""
        self._char_grid.clear()

        for char in self.characters:
            # Add character to all grid cells it overlaps
            min_col = int(char.bbox[0] / self._grid_size)
            max_col = int(char.bbox[2] / self._grid_size)
            min_row = int(char.bbox[1] / self._grid_size)
            max_row = int(char.bbox[3] / self._grid_size)

            for row in range(min_row, max_row + 1):
                for col in range(min_col, max_col + 1):
                    key = (row, col)
                    if key not in self._char_grid:
                        self._char_grid[key] = []
                    self._char_grid[key].append(char)

    def get_char_at_point(self, x: float, y: float) -> Optional[CharacterInfo]:
        """
        Find the character at the given PDF coordinates.

        Uses spatial index for O(1) average lookup.
        """
        # Find grid cell
        row = int(y / self._grid_size)
        col = int(x / self._grid_size)

        candidates = self._char_grid.get((row, col), [])

        for char in candidates:
            if char.contains_point(x, y):
                return char

        return None

    def get_nearest_char(
        self, x: float, y: float, max_distance: float = 20.0
    ) -> Optional[CharacterInfo]:
        """
        Find the nearest character to a point within max_distance.

        Useful when clicking between characters.
        """
        # Check exact hit first
        exact = self.get_char_at_point(x, y)
        if exact:
            return exact

        # Search nearby grid cells
        center_row = int(y / self._grid_size)
        center_col = int(x / self._grid_size)
        search_radius = int(max_distance / self._grid_size) + 1

        best_char = None
        best_dist = float("inf")

        for row in range(center_row - search_radius, center_row + search_radius + 1):
            for col in range(
                center_col - search_radius, center_col + search_radius + 1
            ):
                for char in self._char_grid.get((row, col), []):
                    # Calculate distance to character center
                    cx = (char.bbox[0] + char.bbox[2]) / 2
                    cy = (char.bbox[1] + char.bbox[3]) / 2
                    dist = ((x - cx) ** 2 + (y - cy) ** 2) ** 0.5

                    if dist < best_dist and dist <= max_distance:
                        best_dist = dist
                        best_char = char

        return best_char

    def get_chars_in_range(
        self, start: CharacterInfo, end: CharacterInfo
    ) -> List[CharacterInfo]:
        """
        Get all characters between start and end (inclusive).

        Uses global_index for proper ordering.
        """
        start_idx = start.global_index
        end_idx = end.global_index

        if start_idx > end_idx:
            start_idx, end_idx = end_idx, start_idx

        return self.characters[start_idx : end_idx + 1]

    def get_chars_in_rect(
        self, rect: Tuple[float, float, float, float]
    ) -> List[CharacterInfo]:
        """Get all characters that intersect with a rectangle."""
        x0, y0, x1, y1 = rect
        result = []

        # Find relevant grid cells
        min_row = int(y0 / self._grid_size)
        max_row = int(y1 / self._grid_size)
        min_col = int(x0 / self._grid_size)
        max_col = int(x1 / self._grid_size)

        seen = set()

        for row in range(min_row, max_row + 1):
            for col in range(min_col, max_col + 1):
                for char in self._char_grid.get((row, col), []):
                    if char.global_index in seen:
                        continue

                    # Check intersection
                    if (
                        char.bbox[0] <= x1
                        and char.bbox[2] >= x0
                        and char.bbox[1] <= y1
                        and char.bbox[3] >= y0
                    ):
                        result.append(char)
                        seen.add(char.global_index)

        # Sort by global index
        result.sort(key=lambda c: c.global_index)
        return result

    def get_selection_rects(
        self, selected_chars: List[CharacterInfo]
    ) -> List[Tuple[float, float, float, float]]:
        """
        Generate optimized selection rectangles for painting.

        Merges consecutive characters on the same line.
        """
        if not selected_chars:
            return []

        # Group by line
        lines: Dict[Tuple[int, int], List[CharacterInfo]] = {}
        for char in selected_chars:
            key = (char.block_index, char.line_index)
            if key not in lines:
                lines[key] = []
            lines[key].append(char)

        rects = []

        for line_chars in lines.values():
            # Sort by position
            line_chars.sort(key=lambda c: c.bbox[0])

            # Merge consecutive characters
            current_rect = None

            for char in line_chars:
                if current_rect is None:
                    current_rect = list(char.bbox)
                elif char.bbox[0] - current_rect[2] < 3:  # Small gap tolerance
                    # Extend current rect
                    current_rect[2] = char.bbox[2]
                    current_rect[1] = min(current_rect[1], char.bbox[1])
                    current_rect[3] = max(current_rect[3], char.bbox[3])
                else:
                    # Start new rect
                    rects.append(tuple(current_rect))
                    current_rect = list(char.bbox)

            if current_rect:
                rects.append(tuple(current_rect))

        return rects

    def get_text_from_chars(self, chars: List[CharacterInfo]) -> str:
        """
        Extract text string from a list of characters.

        Preserves line breaks between different lines.
        """
        if not chars:
            return ""

        # Sort by position
        sorted_chars = sorted(chars, key=lambda c: c.global_index)

        lines = []
        current_line = []
        last_line_key = None

        for char in sorted_chars:
            line_key = (char.block_index, char.line_index)

            if last_line_key is not None and line_key != last_line_key:
                # New line
                lines.append("".join(c.char for c in current_line))
                current_line = []

            current_line.append(char)
            last_line_key = line_key

        if current_line:
            lines.append("".join(c.char for c in current_line))

        return "\n".join(lines)

    @property
    def full_text(self) -> str:
        """Get all text on the page."""
        return self.get_text_from_chars(self.characters)

    def __len__(self) -> int:
        return len(self.characters)

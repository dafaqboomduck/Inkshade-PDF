"""
Background worker for PDF search operations.
"""

from typing import List, Optional

import fitz
from PyQt5.QtCore import QThread, pyqtSignal

from .models import SearchResult


class SearchWorker(QThread):
    """Worker thread for searching large PDFs without freezing the UI."""

    # Signals
    progress = pyqtSignal(int, int)  # current_page, total_pages
    result_found = pyqtSignal(object)  # SearchResult
    finished = pyqtSignal(int)  # total results count
    error = pyqtSignal(str)  # error message

    def __init__(self, doc: fitz.Document, search_term: str, parent=None):
        super().__init__(parent)
        self._doc = doc
        self._search_term = search_term
        self._cancelled = False
        self._results: List[SearchResult] = []

    def cancel(self):
        """Cancel the search operation."""
        self._cancelled = True

    def run(self):
        """Execute the search in background thread."""
        try:
            if not self._doc or not self._search_term:
                self.finished.emit(0)
                return

            total_pages = self._doc.page_count

            for page_idx in range(total_pages):
                if self._cancelled:
                    break

                # Emit progress
                self.progress.emit(page_idx + 1, total_pages)

                try:
                    page = self._doc.load_page(page_idx)
                    quads_on_page = page.search_for(self._search_term, quads=True)
                    rects_on_page = [q.rect for q in quads_on_page]
                    merged_rects = self._merge_consecutive_rects(rects_on_page)

                    for rect in merged_rects:
                        rect_tuple = (
                            rect.x0,
                            rect.y0,
                            rect.x1,
                            rect.y1,
                            rect.width,
                            rect.height,
                        )
                        result = SearchResult(
                            page_index=page_idx,
                            rect=rect_tuple,
                            text=self._search_term,
                        )
                        self._results.append(result)
                        self.result_found.emit(result)

                except Exception as e:
                    print(f"Error searching page {page_idx}: {e}")
                    continue

            self.finished.emit(len(self._results))

        except Exception as e:
            self.error.emit(str(e))

    def get_results(self) -> List[SearchResult]:
        """Get all results found so far."""
        return self._results

    def _merge_consecutive_rects(
        self, rects: List[fitz.Rect], y_tolerance: float = 3.0, max_height: float = 18.0
    ) -> List[fitz.Rect]:
        """Groups and merges rectangles on the same line."""
        if not rects:
            return []

        merged_results = []
        rects.sort(key=lambda r: (r.y0, r.x0))

        current_group = [rects[0]]
        current_merged_rect = self._merge_rects(current_group)

        for i in range(1, len(rects)):
            current_rect = rects[i]
            vertical_gap = current_rect.y0 - current_merged_rect.y1
            projected_y1 = max(current_rect.y1, current_merged_rect.y1)
            projected_height = projected_y1 - current_merged_rect.y0
            is_contiguous = (vertical_gap <= y_tolerance) and (
                projected_height <= max_height
            )

            if is_contiguous:
                current_group.append(current_rect)
                current_merged_rect = self._merge_rects(current_group)
            else:
                merged_results.append(current_merged_rect)
                current_group = [current_rect]
                current_merged_rect = self._merge_rects(current_group)

        if current_group:
            merged_results.append(current_merged_rect)

        return merged_results

    def _merge_rects(self, rects: List[fitz.Rect]) -> Optional[fitz.Rect]:
        """Find the bounding box of a list of rectangles."""
        if not rects:
            return None

        min_x0 = min(r.x0 for r in rects)
        min_y0 = min(r.y0 for r in rects)
        max_x1 = max(r.x1 for r in rects)
        max_y1 = max(r.y1 for r in rects)

        return fitz.Rect(min_x0, min_y0, max_x1, max_y1)

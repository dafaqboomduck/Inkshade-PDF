"""
Background worker thread for page-streaming narration.

Runs the :class:`NarrationPipeline` in a ``QThread``, emitting each
page's audio as soon as it's ready so the controller can begin
playback immediately.
"""

import logging
from typing import Optional

from PyQt5.QtCore import QThread, pyqtSignal

from narration.pipeline import (
    NarrationCallbacks,
    NarrationConfig,
    NarrationPipeline,
    NarrationResult,
    PageNarrationResult,
)

logger = logging.getLogger(__name__)


class NarrationWorker(QThread):
    """
    QThread that drives the narration pipeline page-by-page.

    Signals
    -------
    page_audio_ready(int, bytes, object)
        ``(page_index, wav_bytes, PageNarrationResult)`` — emitted as
        soon as each page finishes synthesis.
    phase_changed(str)
        Current phase label for UI display.
    page_progress(int, int)
        ``(current_page, total_pages)`` during processing.
    segment_progress(int, int)
        ``(current_segment, total_segments)`` during TTS for a page.
    all_finished(bool, str, object)
        ``(success, message, NarrationResult|None)`` when done.
    error(str)
        Fatal error message.
    """

    # Signals
    page_audio_ready = pyqtSignal(int, bytes, object)  # page_idx, wav, PageNarrationResult
    phase_changed = pyqtSignal(str)
    page_progress = pyqtSignal(int, int)      # current, total
    segment_progress = pyqtSignal(int, int)   # current, total
    all_finished = pyqtSignal(bool, str, object)  # success, msg, NarrationResult|None
    error = pyqtSignal(str)

    def __init__(
        self,
        pdf_path: str,
        config: Optional[NarrationConfig] = None,
        start_page: int = 0,
        parent=None,
    ):
        super().__init__(parent)
        self._pdf_path = pdf_path
        self._config = config or NarrationConfig()
        self._start_page = start_page
        self._cancelled = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def cancel(self):
        """Request cancellation — the pipeline checks between pages."""
        self._cancelled = True

    @property
    def is_cancelled(self) -> bool:
        return self._cancelled

    # ------------------------------------------------------------------
    # Thread entry point
    # ------------------------------------------------------------------

    def run(self):
        try:
            cfg = self._config

            # Apply start_page to config.page_range
            if self._start_page > 0:
                end = cfg.page_range[1] if cfg.page_range else None
                cfg.page_range = (self._start_page, end)

            pipeline = NarrationPipeline(cfg)

            # Build callbacks that bridge to Qt signals
            callbacks = NarrationCallbacks(
                on_phase=lambda phase: self.phase_changed.emit(phase),
                on_page=lambda cur, total: self.page_progress.emit(cur, total),
                on_segment=lambda cur, total: self.segment_progress.emit(cur, total),
                on_cancelled=lambda: self._cancelled,
            )

            # Drive the page-streaming generator
            gen = pipeline.narrate_pages(self._pdf_path, callbacks=callbacks)
            final_result: Optional[NarrationResult] = None

            try:
                while True:
                    page_result: PageNarrationResult = next(gen)
                    if self._cancelled:
                        break
                    self.page_audio_ready.emit(
                        page_result.page_index,
                        page_result.wav_bytes,
                        page_result,
                    )
            except StopIteration as e:
                final_result = e.value

            if self._cancelled:
                self.all_finished.emit(False, "Narration cancelled.", None)
            else:
                self.all_finished.emit(
                    True,
                    "Narration complete.",
                    final_result,
                )

        except Exception as e:
            logger.exception("NarrationWorker error: %s", e)
            self.error.emit(str(e))
            self.all_finished.emit(False, f"Error: {e}", None)

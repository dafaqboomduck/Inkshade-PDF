"""
Narration controller: manages audio queue, playback, and worker lifecycle.

Coordinates the :class:`NarrationWorker` background thread with
``QMediaPlayer`` playback, providing seamless page-to-page audio
streaming with play/pause/stop/speed controls.
"""

import logging
import os
import tempfile
from typing import Dict, List, Optional

from PyQt5.QtCore import QBuffer, QByteArray, QObject, QThread, QTimer, QUrl, pyqtSignal

try:
    from PyQt5.QtMultimedia import QMediaContent, QMediaPlayer
    _HAS_MULTIMEDIA = True
except ImportError:
    _HAS_MULTIMEDIA = False
    QMediaContent = None  # type: ignore[assignment,misc]
    QMediaPlayer = None   # type: ignore[assignment,misc]

from core.narration.narration_worker import NarrationWorker
from narration.pipeline import (
    NarrationConfig,
    NarrationResult,
    PageNarrationResult,
)
from narration.tts.model_manager import ModelManager

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------
# Voice download worker
# ------------------------------------------------------------------


class VoiceDownloadWorker(QThread):
    """Downloads a voice model in the background."""

    download_progress = pyqtSignal(int, int)     # bytes_done, bytes_total
    download_finished = pyqtSignal(str)           # voice model path
    download_error = pyqtSignal(str)

    def __init__(self, voice_name: str, voice_dir=None, parent=None):
        super().__init__(parent)
        self._voice_name = voice_name
        self._voice_dir = voice_dir

    def run(self):
        try:
            mgr = ModelManager(voice_dir=self._voice_dir)
            path = mgr.ensure_voice_available(self._voice_name)
            self.download_finished.emit(str(path))
        except Exception as e:
            self.download_error.emit(str(e))


# ------------------------------------------------------------------
# Export audio worker
# ------------------------------------------------------------------


class ExportAudioWorker(QThread):
    """Combines page WAVs and exports as MP3/WAV in a background thread."""

    export_progress = pyqtSignal(int, int)  # current_page, total_pages
    export_finished = pyqtSignal(str)       # output path
    export_error = pyqtSignal(str)

    def __init__(
        self,
        audio_queue: Dict[int, "PageNarrationResult"],
        page_order: List[int],
        output_path: str,
        parent=None,
    ):
        super().__init__(parent)
        self._audio_queue = audio_queue
        self._page_order = page_order
        self._output_path = output_path

    def run(self):
        try:
            from narration.tts.audio_builder import AudioBuilder

            builder = AudioBuilder()
            total = len(self._page_order)

            for i, page_idx in enumerate(self._page_order):
                result = self._audio_queue.get(page_idx)
                if result and result.wav_bytes and len(result.wav_bytes) > 44:
                    builder.add_speech(result.wav_bytes)
                self.export_progress.emit(i + 1, total)

            if builder.is_empty:
                self.export_error.emit("No audio content to export.")
                return

            builder.normalize()
            builder.apply_crossfade()

            if self._output_path.lower().endswith(".wav"):
                builder.export_wav(self._output_path)
            else:
                builder.export_mp3(self._output_path)

            self.export_finished.emit(self._output_path)
        except Exception as e:
            self.export_error.emit(str(e))


class NarrationController(QObject):
    """
    Central coordinator for narration playback.

    Manages the audio queue, drives ``QMediaPlayer`` playback, and
    bridges worker signals to UI signals.
    """

    # --- Signals exposed to UI ----------------------------------------
    narration_started = pyqtSignal(int)                 # total pages
    page_ready = pyqtSignal(int)                        # page audio buffered
    playback_started = pyqtSignal(int)                  # playing page N
    playback_paused = pyqtSignal()
    playback_resumed = pyqtSignal()
    playback_stopped = pyqtSignal()
    playback_position_changed = pyqtSignal(int, float)  # (page_index, position_ms)
    instruction_changed = pyqtSignal(int, int, list)    # (page_idx, instr_idx, characters)
    processing_progress = pyqtSignal(int, int, str)     # (current, total, phase_label)
    buffering = pyqtSignal(bool)                        # True = waiting for next page
    narration_finished = pyqtSignal(object)             # NarrationResult
    narration_error = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)

        # --- Internal state -------------------------------------------
        self._worker: Optional[NarrationWorker] = None
        self._config: NarrationConfig = NarrationConfig()

        # Audio queue: page_index → result
        self._audio_queue: Dict[int, PageNarrationResult] = {}
        self._page_order: List[int] = []

        # Playback state
        self._current_playback_page: int = -1
        self._current_instruction_idx: int = -1
        self._playback_speed: float = 1.0
        self._is_playing: bool = False
        self._is_paused: bool = False
        self._waiting_for_buffer: bool = False

        # Final result from worker
        self._last_result: Optional[NarrationResult] = None
        self._worker_done: bool = False
        self._total_pages: int = 0

        # Phase label for progress
        self._current_phase: str = ""

        # Media player
        self._player: Optional[QMediaPlayer] = None
        self._temp_files: List[str] = []

        # Position polling timer
        self._position_timer = QTimer(self)
        self._position_timer.setInterval(100)  # 100ms tick
        self._position_timer.timeout.connect(self._on_position_tick)

        # Dependencies availability flag
        self._dependencies_available: Optional[bool] = None
        self._missing_deps: List[str] = []
        self._check_dependencies()

    # ------------------------------------------------------------------
    # Dependency checking
    # ------------------------------------------------------------------

    def _check_dependencies(self):
        """Check if narration-specific packages are importable."""
        self._missing_deps = []
        for mod_name, pkg_name in [
            ("piper", "piper-tts"),
            ("ultralytics", "ultralytics"),
            ("pydub", "pydub"),
        ]:
            try:
                __import__(mod_name)
            except ImportError:
                self._missing_deps.append(pkg_name)
        self._dependencies_available = len(self._missing_deps) == 0

    @property
    def dependencies_available(self) -> bool:
        if self._dependencies_available is None:
            self._check_dependencies()
        return self._dependencies_available

    @property
    def missing_dependencies(self) -> List[str]:
        return list(self._missing_deps)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start_narration(self, pdf_path: str, start_page: int = 0):
        """
        Validate, create worker, and start the background thread.

        Playback auto-starts when the first page arrives.
        """
        # Dependency check
        if not self.dependencies_available:
            self.narration_error.emit(
                "Missing dependencies: " + ", ".join(self._missing_deps)
                + "\nInstall with: pip install " + " ".join(self._missing_deps)
            )
            return

        if self.is_running():
            self.stop()

        # Reset state
        self._audio_queue.clear()
        self._page_order.clear()
        self._current_playback_page = -1
        self._current_instruction_idx = -1
        self._is_playing = False
        self._is_paused = False
        self._waiting_for_buffer = False
        self._worker_done = False
        self._last_result = None
        self._cleanup_temp_files()

        # Create media player
        if self._player is None:
            self._player = QMediaPlayer(self)
            self._player.mediaStatusChanged.connect(self._on_media_status_changed)

        # Create and start worker
        self._worker = NarrationWorker(
            pdf_path=pdf_path,
            config=self._config,
            start_page=start_page,
            parent=None,  # No parent — we manage lifecycle manually
        )
        self._worker.page_audio_ready.connect(self._on_page_audio_ready)
        self._worker.phase_changed.connect(self._on_phase_changed)
        self._worker.page_progress.connect(self._on_page_progress)
        self._worker.segment_progress.connect(self._on_segment_progress)
        self._worker.all_finished.connect(self._on_worker_finished)
        self._worker.error.connect(self._on_worker_error)

        self._worker.start()
        self.narration_started.emit(0)  # total not yet known; updated via page_progress

    def stop(self):
        """Stop playback AND cancel the worker."""
        # Stop playback
        if self._player:
            self._player.stop()

        self._position_timer.stop()

        # Cancel worker
        if self._worker and self._worker.isRunning():
            self._worker.cancel()
            self._worker.wait(5000)

        self._worker = None
        self._is_playing = False
        self._is_paused = False
        self._waiting_for_buffer = False
        self._cleanup_temp_files()

        self.playback_stopped.emit()

    def pause(self):
        """Pause QMediaPlayer. Worker keeps synthesising in background."""
        if self._player and self._is_playing:
            self._player.pause()
            self._is_paused = True
            self._position_timer.stop()
            self.playback_paused.emit()

    def resume(self):
        """Resume playback."""
        if self._player and self._is_paused:
            self._player.play()
            self._is_paused = False
            self._position_timer.start()
            self.playback_resumed.emit()

    def toggle_pause(self):
        """Convenience for a single play/pause button."""
        if self._is_paused:
            self.resume()
        elif self._is_playing:
            self.pause()

    def set_playback_speed(self, factor: float):
        """Update QMediaPlayer playback rate (0.5× – 3.0×)."""
        self._playback_speed = max(0.5, min(3.0, factor))
        if self._player:
            self._player.setPlaybackRate(self._playback_speed)

    def seek_to_page(self, page_index: int):
        """Jump playback to a specific page (if its audio is ready)."""
        if page_index in self._audio_queue:
            self._play_page(page_index)

    def seek_position(self, position_ms: int):
        """Seek within the current page's audio."""
        if self._player:
            self._player.setPosition(position_ms)

    def is_running(self) -> bool:
        """True if worker is alive or playback is active."""
        worker_alive = self._worker is not None and self._worker.isRunning()
        return worker_alive or self._is_playing

    def is_playing(self) -> bool:
        """True if audio is actively playing (not paused)."""
        return self._is_playing and not self._is_paused

    def update_config(self, **kwargs):
        """Merge keyword arguments into the current config."""
        for key, value in kwargs.items():
            if hasattr(self._config, key):
                setattr(self._config, key, value)

    def get_page_duration(self, page_index: int) -> float:
        """Get the duration in seconds of a buffered page, or 0."""
        result = self._audio_queue.get(page_index)
        return result.duration_seconds if result else 0.0

    def get_current_page(self) -> int:
        return self._current_playback_page

    def get_audio_queue(self) -> Dict[int, PageNarrationResult]:
        """Return the full audio queue (for export)."""
        return self._audio_queue

    def get_page_order(self) -> List[int]:
        """Return the ordered list of page indices with audio."""
        return self._page_order

    # ------------------------------------------------------------------
    # Internal — worker signal handlers
    # ------------------------------------------------------------------

    def _on_page_audio_ready(self, page_index: int, wav_bytes: bytes, result: PageNarrationResult):
        """Handle a page's audio arriving from the worker."""
        self._audio_queue[page_index] = result
        self._page_order.append(page_index)
        self._page_order.sort()

        self.page_ready.emit(page_index)

        # If nothing is playing, start playback
        if not self._is_playing and not self._is_paused:
            if wav_bytes and len(wav_bytes) > 44:
                self._play_page(page_index)
            return

        # If we're waiting for the next page, resume
        if self._waiting_for_buffer:
            next_page = self._current_playback_page + 1
            if page_index == next_page and wav_bytes and len(wav_bytes) > 44:
                self._waiting_for_buffer = False
                self.buffering.emit(False)
                self._play_page(next_page)

    def _on_phase_changed(self, phase: str):
        self._current_phase = phase
        self.processing_progress.emit(0, 0, phase)

    def _on_page_progress(self, current: int, total: int):
        self._total_pages = total
        self.processing_progress.emit(current, total, self._current_phase)

    def _on_segment_progress(self, current: int, total: int):
        # Could be wired to a more granular UI indicator
        pass

    def _on_worker_finished(self, success: bool, message: str, result: object):
        self._worker_done = True
        self._last_result = result
        if result:
            self.narration_finished.emit(result)
        if not success and not self._is_playing:
            self.narration_error.emit(message)

    def _on_worker_error(self, message: str):
        self.narration_error.emit(message)

    # ------------------------------------------------------------------
    # Internal — playback
    # ------------------------------------------------------------------

    def _play_page(self, page_index: int):
        """Load and play audio for the given page."""
        result = self._audio_queue.get(page_index)
        if not result or not result.wav_bytes or len(result.wav_bytes) <= 44:
            # Skip empty pages — try the next one
            next_page = page_index + 1
            if next_page in self._audio_queue:
                self._play_page(next_page)
            elif not self._worker_done:
                self._current_playback_page = page_index
                self._waiting_for_buffer = True
                self.buffering.emit(True)
            else:
                # All done
                self._finish_playback()
            return

        # Write WAV to temp file for QMediaPlayer
        fd, tmp_path = tempfile.mkstemp(suffix=".wav")
        os.close(fd)
        with open(tmp_path, "wb") as f:
            f.write(result.wav_bytes)
        self._temp_files.append(tmp_path)

        # Load and play
        url = QUrl.fromLocalFile(tmp_path)
        self._player.setMedia(QMediaContent(url))
        self._player.setPlaybackRate(self._playback_speed)
        self._player.play()

        self._current_playback_page = page_index
        self._current_instruction_idx = -1
        self._is_playing = True
        self._is_paused = False

        self._position_timer.start()
        self.playback_started.emit(page_index)

    def _on_media_status_changed(self, status):
        """Handle media player status transitions."""
        if status == QMediaPlayer.EndOfMedia:
            # Current page finished — try the next one
            next_page = self._get_next_page(self._current_playback_page)
            if next_page is not None and next_page in self._audio_queue:
                self._play_page(next_page)
            elif next_page is not None and not self._worker_done:
                # Next page exists but not yet synthesised
                self._waiting_for_buffer = True
                self.buffering.emit(True)
            else:
                # No more pages — finished
                self._finish_playback()

    def _get_next_page(self, current_page: int) -> Optional[int]:
        """Get the next page index in the ordered page list, or None."""
        try:
            idx = self._page_order.index(current_page)
            if idx + 1 < len(self._page_order):
                return self._page_order[idx + 1]
        except ValueError:
            pass

        # Try sequential
        next_p = current_page + 1
        if next_p in self._audio_queue:
            return next_p
        if not self._worker_done:
            return next_p  # Expected but not yet ready
        return None

    def _finish_playback(self):
        """All pages played — clean up playback state."""
        self._position_timer.stop()
        self._is_playing = False
        self._is_paused = False
        self.playback_stopped.emit()

    def _on_position_tick(self):
        """Poll QMediaPlayer position and emit updates."""
        if not self._player or not self._is_playing:
            return

        position_ms = self._player.position()
        self.playback_position_changed.emit(
            self._current_playback_page, float(position_ms)
        )

        # Determine active instruction from timing offsets
        result = self._audio_queue.get(self._current_playback_page)
        if result and result.timing_offsets:
            new_idx = self._current_instruction_idx
            for start_ms, end_ms, instr_idx in result.timing_offsets:
                if start_ms <= position_ms <= end_ms:
                    new_idx = instr_idx
                    break

            if new_idx != self._current_instruction_idx:
                self._current_instruction_idx = new_idx
                # Get characters for the current instruction
                chars = []
                if (
                    result.instructions
                    and 0 <= new_idx < len(result.instructions)
                ):
                    chars = result.instructions[new_idx].characters
                self.instruction_changed.emit(
                    self._current_playback_page, new_idx, chars
                )

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def _cleanup_temp_files(self):
        """Remove any temporary WAV files."""
        for path in self._temp_files:
            try:
                if os.path.exists(path):
                    os.unlink(path)
            except OSError:
                pass
        self._temp_files.clear()

    def cleanup(self):
        """Full cleanup — call when the controller is being destroyed."""
        self.stop()
        self._cleanup_temp_files()

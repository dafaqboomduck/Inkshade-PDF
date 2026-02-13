"""
Audio builder: assembles synthesised speech chunks and silence gaps
into a single continuous audio file, then exports as MP3 or WAV.
"""

import io
import logging
from pathlib import Path

from pydub import AudioSegment

logger = logging.getLogger(__name__)


class AudioBuilder:
    """
    Incrementally builds an audio track from WAV speech chunks and
    silence gaps.

    Usage::

        builder = AudioBuilder(sample_rate=22050)
        builder.add_silence(1.5)
        builder.add_speech(wav_bytes)
        builder.normalize()
        builder.export_mp3("output.mp3")
    """

    def __init__(self, sample_rate: int = 22050):
        self._sample_rate = sample_rate
        self._audio = AudioSegment.empty()

    def add_silence(self, duration_seconds: float) -> None:
        """Append silence of the given duration."""
        if duration_seconds <= 0:
            return
        ms = int(duration_seconds * 1000)
        self._audio += AudioSegment.silent(duration=ms, frame_rate=self._sample_rate)

    def add_speech(self, wav_bytes: bytes) -> None:
        """Append a WAV speech chunk produced by :class:`TTSEngine`."""
        if not wav_bytes or len(wav_bytes) <= 44:
            return
        self._audio += AudioSegment.from_wav(io.BytesIO(wav_bytes))

    def normalize(self, target_dBFS: float = -20.0) -> None:
        """Normalize volume to *target_dBFS*."""
        if len(self._audio) == 0:
            return
        current = self._audio.dBFS
        if current == float("-inf"):
            return
        self._audio = self._audio.apply_gain(target_dBFS - current)

    def apply_crossfade(self, ms: int = 50) -> None:
        """Apply fade-in/out to smooth the track boundaries."""
        if len(self._audio) == 0 or ms <= 0:
            return
        self._audio = self._audio.fade_in(ms).fade_out(ms)

    def export_mp3(self, output_path: str, bitrate: str = "192k") -> None:
        """Export assembled audio as MP3."""
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self._audio.export(str(path), format="mp3", bitrate=bitrate)
        self._log_export(path)

    def export_wav(self, output_path: str) -> None:
        """Export assembled audio as WAV."""
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self._audio.export(str(path), format="wav")
        self._log_export(path)

    def _log_export(self, path: Path) -> None:
        dur = self.get_duration()
        size_mb = path.stat().st_size / (1024 * 1024)
        logger.info(
            "Exported %s: %.1fs (%.1f min), %.1f MB",
            path,
            dur,
            dur / 60,
            size_mb,
        )

    def get_duration(self) -> float:
        """Current total duration in seconds."""
        return len(self._audio) / 1000.0

    @property
    def is_empty(self) -> bool:
        return len(self._audio) == 0

    def __repr__(self) -> str:
        return f"AudioBuilder(duration={self.get_duration():.1f}s)"

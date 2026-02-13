"""
Piper TTS engine wrapper.

Synthesises text to WAV audio with variable speed control via
Piper's ``length_scale`` parameter.
"""

import io
import wave
from pathlib import Path
from typing import Union


class TTSEngine:
    """
    Speech synthesis with per-segment speed control.

    Usage::

        engine = TTSEngine("voices/en_US-lessac-medium.onnx")
        wav_bytes = engine.synthesize("Hello world", speed_factor=0.9)
    """

    def __init__(self, voice_model_path: Union[str, Path]):
        """
        Load a Piper voice model.

        Args:
            voice_model_path: Path to the ``.onnx`` voice file.

        Raises:
            FileNotFoundError: If the model file does not exist.
            ImportError: If ``piper-tts`` is not installed.
        """
        path = Path(voice_model_path)
        if not path.exists():
            raise FileNotFoundError(f"Voice model not found: {path}")

        try:
            from piper import PiperVoice
        except ImportError:
            raise ImportError(
                "piper-tts is required. Install with: pip install piper-tts"
            )

        self._voice = PiperVoice.load(str(path))
        self._sample_rate: int = self._voice.config.sample_rate
        self._sample_width: int = 2  # 16-bit PCM
        self._channels: int = 1

    @property
    def sample_rate(self) -> int:
        return self._sample_rate

    @property
    def sample_width(self) -> int:
        return self._sample_width

    @property
    def channels(self) -> int:
        return self._channels

    def synthesize(self, text: str, speed_factor: float = 1.0) -> bytes:
        """
        Synthesise *text* to WAV bytes.

        Args:
            text:         Text to speak.
            speed_factor: Speed multiplier (>1 = faster, <1 = slower).

        Returns:
            Complete WAV file as bytes (16-bit mono PCM).
        """
        if not text or not text.strip():
            return self.generate_silence(0.0)

        self._voice.config.length_scale = 1.0 / max(speed_factor, 0.1)

        pcm_parts = []
        for chunk in self._voice.synthesize(text):
            pcm_parts.append(chunk.audio_int16_bytes)

        if not pcm_parts:
            return self.generate_silence(0.0)

        return self._wrap_wav(b"".join(pcm_parts))

    def generate_silence(self, duration_seconds: float) -> bytes:
        """Generate a WAV file containing *duration_seconds* of silence."""
        num_samples = int(self._sample_rate * max(0, duration_seconds))
        pcm_data = b"\x00\x00" * num_samples
        return self._wrap_wav(pcm_data)

    def get_audio_duration(self, wav_bytes: bytes) -> float:
        """Return the duration in seconds of a WAV byte string."""
        try:
            buf = io.BytesIO(wav_bytes)
            with wave.open(buf, "rb") as wf:
                frames = wf.getnframes()
                rate = wf.getframerate()
                return frames / rate if rate > 0 else 0.0
        except Exception:
            return 0.0

    def _wrap_wav(self, pcm_data: bytes) -> bytes:
        """Wrap raw 16-bit mono PCM in a WAV container."""
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(self._channels)
            wf.setsampwidth(self._sample_width)
            wf.setframerate(self._sample_rate)
            wf.writeframes(pcm_data)
        return buf.getvalue()

    def __repr__(self) -> str:
        return (
            f"TTSEngine(rate={self._sample_rate}Hz, {self._sample_width * 8}bit, mono)"
        )

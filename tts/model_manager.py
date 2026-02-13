"""
Piper voice model manager.

Downloads, caches, and locates Piper TTS voice models.
Voice files are stored under ``~/.local/share/InkshadePDF/voices/``.
"""

import logging
import urllib.request
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

_PIPER_VOICES_BASE = "https://huggingface.co/rhasspy/piper-voices/resolve/main"
_DEFAULT_VOICE_DIR = Path.home() / ".local" / "share" / "InkshadePDF" / "voices"

KNOWN_VOICES: Dict[str, Dict[str, str]] = {
    "en_US-lessac-medium": {
        "lang": "en",
        "code": "en_US",
        "name": "lessac",
        "quality": "medium",
    },
    "en_US-lessac-high": {
        "lang": "en",
        "code": "en_US",
        "name": "lessac",
        "quality": "high",
    },
    "en_US-amy-medium": {
        "lang": "en",
        "code": "en_US",
        "name": "amy",
        "quality": "medium",
    },
    "en_US-ryan-medium": {
        "lang": "en",
        "code": "en_US",
        "name": "ryan",
        "quality": "medium",
    },
    "en_GB-alan-medium": {
        "lang": "en",
        "code": "en_GB",
        "name": "alan",
        "quality": "medium",
    },
}
"""Voices with known HuggingFace download paths."""


class ModelManager:
    """
    Manages Piper TTS voice model downloads and caching.

    Usage::

        mgr = ModelManager()
        path = mgr.ensure_voice_available("en_US-lessac-medium")
        engine = TTSEngine(path)
    """

    def __init__(self, voice_dir: Optional[Path] = None):
        self.voice_dir = voice_dir or _DEFAULT_VOICE_DIR
        self.voice_dir.mkdir(parents=True, exist_ok=True)

    def get_voice_path(self, voice_name: str) -> Path:
        """Expected local path for a voice ``.onnx`` file (may not exist yet)."""
        return self.voice_dir / voice_name / f"{voice_name}.onnx"

    def is_voice_available(self, voice_name: str) -> bool:
        """Check whether both the model and config are cached locally."""
        onnx = self.get_voice_path(voice_name)
        return onnx.exists() and onnx.with_suffix(".onnx.json").exists()

    def ensure_voice_available(self, voice_name: str) -> Path:
        """
        Download the voice model if not already cached.

        Args:
            voice_name: A key from :data:`KNOWN_VOICES`.

        Returns:
            Path to the ``.onnx`` model file.

        Raises:
            ValueError:    If *voice_name* is not recognised.
            RuntimeError:  If the download fails.
        """
        if self.is_voice_available(voice_name):
            return self.get_voice_path(voice_name)

        if voice_name not in KNOWN_VOICES:
            raise ValueError(
                f"Unknown voice '{voice_name}'. Available: {list(KNOWN_VOICES.keys())}"
            )

        info = KNOWN_VOICES[voice_name]
        voice_subdir = self.voice_dir / voice_name
        voice_subdir.mkdir(parents=True, exist_ok=True)

        base_url = (
            f"{_PIPER_VOICES_BASE}/"
            f"{info['lang']}/{info['code']}/{info['name']}/{info['quality']}"
        )
        onnx_path = voice_subdir / f"{voice_name}.onnx"
        config_path = voice_subdir / f"{voice_name}.onnx.json"

        logger.info("Downloading voice model: %s", voice_name)
        self._download(f"{base_url}/{voice_name}.onnx", onnx_path, "model")
        self._download(f"{base_url}/{voice_name}.onnx.json", config_path, "config")
        logger.info("Voice ready: %s", onnx_path)

        return onnx_path

    def list_available_voices(self) -> List[str]:
        """Names of locally cached voice models."""
        voices = []
        if not self.voice_dir.exists():
            return voices
        for d in sorted(self.voice_dir.iterdir()):
            if d.is_dir() and (d / f"{d.name}.onnx").exists():
                voices.append(d.name)
        return voices

    def list_known_voices(self) -> List[str]:
        """Names of all known downloadable voices."""
        return list(KNOWN_VOICES.keys())

    @staticmethod
    def _download(url: str, dest: Path, label: str = "file") -> None:
        """Download a file with progress reporting."""
        logger.info("  Fetching %s: %s", label, url)
        try:

            def _progress(block_num, block_size, total_size):
                if total_size > 0:
                    pct = min(100, block_num * block_size * 100 // total_size)
                    size_mb = total_size / (1024 * 1024)
                    print(
                        f"\r  Progress: {pct}% of {size_mb:.1f} MB",
                        end="",
                        flush=True,
                    )

            urllib.request.urlretrieve(url, str(dest), reporthook=_progress)
            print()
        except Exception as e:
            if dest.exists():
                dest.unlink()
            raise RuntimeError(f"Failed to download {label} from {url}: {e}") from e

    def __repr__(self) -> str:
        cached = len(self.list_available_voices())
        return f"ModelManager(dir='{self.voice_dir}', cached={cached})"

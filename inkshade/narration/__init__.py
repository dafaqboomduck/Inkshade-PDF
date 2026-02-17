"""
Inkshade PDF Narration pipeline.

Layout detection, reading script generation, TTS synthesis, and audio
assembly for producing narrated audio from PDF documents.
"""

from .pipeline import (
    NarrationCallbacks,
    NarrationConfig,
    NarrationPipeline,
    NarrationResult,
    PageNarrationResult,
)

__all__ = [
    "NarrationCallbacks",
    "NarrationConfig",
    "NarrationPipeline",
    "NarrationResult",
    "PageNarrationResult",
]

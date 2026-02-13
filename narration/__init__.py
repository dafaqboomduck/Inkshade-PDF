"""
Inkshade PDF Narration pipeline.

Layout detection, reading script generation, TTS synthesis, and audio
assembly for producing narrated audio from PDF documents.
"""

from .pipeline import NarrationConfig, NarrationPipeline, NarrationResult

__all__ = [
    "NarrationPipeline",
    "NarrationConfig",
    "NarrationResult",
]

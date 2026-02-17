"""
Qt-aware narration components: worker thread and controller.

Re-exports the backend pipeline types for convenience.
"""

from narration.pipeline import (
    NarrationCallbacks,
    NarrationConfig,
    NarrationPipeline,
    NarrationResult,
    PageNarrationResult,
)

from .narration_worker import NarrationWorker

__all__ = [
    "NarrationCallbacks",
    "NarrationConfig",
    "NarrationPipeline",
    "NarrationResult",
    "NarrationWorker",
    "PageNarrationResult",
]

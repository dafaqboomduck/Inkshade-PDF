"""
Application controllers for managing interactions between UI and core logic.
"""

from .annotation_controller import AnnotationController
from .input_handler import UserInputHandler
from .link_handler import LinkNavigationHandler
from .view_controller import ViewController

try:
    from .narration_controller import NarrationController
except ImportError:
    NarrationController = None  # type: ignore[assignment,misc]

__all__ = [
    "UserInputHandler",
    "ViewController",
    "AnnotationController",
    "LinkNavigationHandler",
    "NarrationController",
]

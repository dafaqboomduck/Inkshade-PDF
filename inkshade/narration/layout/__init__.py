"""Document layout detection and block classification."""

from .block_matcher import compute_iou, match_regions_to_blocks
from .classifier import classify_document, classify_page
from .detector import LayoutDetector
from .feature_refiner import detect_running_headers_footers, refine_classifications
from .models import ClassifiedBlock, LayoutLabel, LayoutRegion

__all__ = [
    "LayoutDetector",
    "LayoutLabel",
    "LayoutRegion",
    "ClassifiedBlock",
    "classify_page",
    "classify_document",
    "match_regions_to_blocks",
    "compute_iou",
    "refine_classifications",
    "detect_running_headers_footers",
]

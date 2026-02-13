"""
High-level page classification: detection → matching → refinement.

This is the main entry point for layout analysis consumed by the pipeline.
"""

from typing import Dict, List, Tuple

from PIL import Image

from core.page.models import BlockInfo

from .block_matcher import match_regions_to_blocks
from .detector import LayoutDetector
from .feature_refiner import detect_running_headers_footers, refine_classifications
from .models import ClassifiedBlock


def classify_page(
    detector: LayoutDetector,
    page_image: Image.Image,
    blocks: List[BlockInfo],
    page_width: float,
    page_height: float,
    scale: float = 1.5,
    confidence: float = 0.35,
    iou_threshold: float = 0.1,
    overlap_threshold: float = 0.5,
) -> List[ClassifiedBlock]:
    """
    Classify every text block on a single page.

    Chains YOLO detection → block matching → typographic refinement.

    Returns:
        One ``ClassifiedBlock`` per input block, in the same order.
    """
    regions = detector.detect(page_image, confidence=confidence)

    classified = match_regions_to_blocks(
        regions,
        blocks,
        scale,
        iou_threshold=iou_threshold,
        overlap_threshold=overlap_threshold,
    )

    refine_classifications(classified, page_width, page_height)
    return classified


def classify_document(
    detector: LayoutDetector,
    pdf_adapter,
    scale: float = 1.5,
    confidence: float = 0.35,
    page_range: Tuple[int, int] = None,
) -> Dict[int, List[ClassifiedBlock]]:
    """
    Classify all pages in a document.

    After per-page classification, applies cross-page running
    header/footer detection when three or more pages are available.

    Returns:
        Dict mapping page index → list of ``ClassifiedBlock``.
    """
    start = page_range[0] if page_range else 0
    end = page_range[1] if page_range else pdf_adapter.page_count - 1
    end = min(end, pdf_adapter.page_count - 1)

    result: Dict[int, List[ClassifiedBlock]] = {}
    page_heights: Dict[int, float] = {}

    for idx in range(start, end + 1):
        img = pdf_adapter.render(idx, scale=scale)
        blocks = pdf_adapter.text_structure(idx)
        w, h = pdf_adapter.dimensions(idx)
        page_heights[idx] = h

        classified = classify_page(
            detector,
            img,
            blocks,
            w,
            h,
            scale=scale,
            confidence=confidence,
        )
        result[idx] = classified

    if len(result) >= 3:
        detect_running_headers_footers(result, page_heights)

    return result

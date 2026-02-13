"""
Maps YOLO layout regions to text-layer BlockInfo objects.

The detector works in pixel space (rendered image) while BlockInfo
bounding boxes live in PDF point space.  This module handles coordinate
conversion and IoU-based assignment.
"""

from typing import List, Tuple

from core.page.models import BlockInfo

from .models import ClassifiedBlock, LayoutLabel, LayoutRegion


def _bbox_intersection(
    a: Tuple[float, float, float, float],
    b: Tuple[float, float, float, float],
) -> float:
    """Area of the intersection rectangle (0 if no overlap)."""
    x0 = max(a[0], b[0])
    y0 = max(a[1], b[1])
    x1 = min(a[2], b[2])
    y1 = min(a[3], b[3])
    if x1 <= x0 or y1 <= y0:
        return 0.0
    return (x1 - x0) * (y1 - y0)


def _bbox_area(bbox: Tuple[float, float, float, float]) -> float:
    return max(0, bbox[2] - bbox[0]) * max(0, bbox[3] - bbox[1])


def compute_iou(
    a: Tuple[float, float, float, float],
    b: Tuple[float, float, float, float],
) -> float:
    """Intersection-over-Union between two axis-aligned boxes."""
    inter = _bbox_intersection(a, b)
    if inter == 0:
        return 0.0
    union = _bbox_area(a) + _bbox_area(b) - inter
    return inter / union if union > 0 else 0.0


def compute_overlap_ratio(
    block_bbox: Tuple[float, float, float, float],
    region_bbox: Tuple[float, float, float, float],
) -> float:
    """Fraction of *block_bbox* area covered by *region_bbox*."""
    inter = _bbox_intersection(block_bbox, region_bbox)
    area = _bbox_area(block_bbox)
    return inter / area if area > 0 else 0.0


def regions_to_pdf_coords(
    regions: List[LayoutRegion],
    scale: float,
) -> List[LayoutRegion]:
    """Convert region bboxes from pixel space to PDF point space."""
    return [
        LayoutRegion(
            label=r.label,
            confidence=r.confidence,
            bbox=(
                r.bbox[0] / scale,
                r.bbox[1] / scale,
                r.bbox[2] / scale,
                r.bbox[3] / scale,
            ),
        )
        for r in regions
    ]


def match_regions_to_blocks(
    regions: List[LayoutRegion],
    blocks: List[BlockInfo],
    scale: float,
    iou_threshold: float = 0.1,
    overlap_threshold: float = 0.5,
) -> List[ClassifiedBlock]:
    """
    Assign a layout label to each text block based on YOLO detections.

    Uses a two-pass strategy:

    1. **IoU pass** — each block gets the label of the region with the
       highest IoU, provided it exceeds *iou_threshold*.
    2. **Overlap pass** — unmatched blocks are assigned the label of the
       region covering the largest fraction of the block's area (above
       *overlap_threshold*), with a slight confidence penalty.

    Blocks with no match receive ``LayoutLabel.UNKNOWN``.

    Args:
        regions:           Detected layout regions (pixel coords).
        blocks:            Text blocks from ``PageTextLayer`` (PDF coords).
        scale:             Render scale used to produce the page image.
        iou_threshold:     Minimum IoU for pass 1.
        overlap_threshold: Minimum block-overlap ratio for pass 2.

    Returns:
        One ``ClassifiedBlock`` per input block, in the same order.
    """
    pdf_regions = regions_to_pdf_coords(regions, scale)
    classified: List[ClassifiedBlock] = []

    for block in blocks:
        best_iou = 0.0
        best_overlap = 0.0
        best_region_iou = None
        best_region_overlap = None

        for region, orig_region in zip(pdf_regions, regions):
            iou = compute_iou(block.bbox, region.bbox)
            if iou > best_iou:
                best_iou = iou
                best_region_iou = (region, orig_region)

            overlap = compute_overlap_ratio(block.bbox, region.bbox)
            if overlap > best_overlap:
                best_overlap = overlap
                best_region_overlap = (region, orig_region)

        if best_iou >= iou_threshold and best_region_iou is not None:
            region, orig = best_region_iou
            classified.append(
                ClassifiedBlock(
                    block=block,
                    label=region.label,
                    confidence=region.confidence,
                    source_region=orig,
                )
            )
            continue

        if best_overlap >= overlap_threshold and best_region_overlap is not None:
            region, orig = best_region_overlap
            classified.append(
                ClassifiedBlock(
                    block=block,
                    label=region.label,
                    confidence=region.confidence * 0.9,
                    source_region=orig,
                )
            )
            continue

        classified.append(
            ClassifiedBlock(
                block=block,
                label=LayoutLabel.UNKNOWN,
                confidence=0.0,
            )
        )

    return classified

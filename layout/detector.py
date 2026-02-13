"""
YOLOv8 DocLayNet layout detector.

Wraps ultralytics YOLO to detect document layout regions (title,
heading, body text, footnotes, tables, etc.) from rendered page images.

If the model weights are not found locally, they are automatically
downloaded from HuggingFace.
"""

import logging
import urllib.request
from pathlib import Path
from typing import List, Optional, Union

import numpy as np
from PIL import Image
from ultralytics import YOLO

from .models import DOCLAYNET_INDEX_TO_LABEL, LayoutLabel, LayoutRegion

logger = logging.getLogger(__name__)

_DEFAULT_MODEL_DIR = Path(__file__).resolve().parents[2] / "models"
_DEFAULT_MODEL_NAME = "yolov8x_doclaynet.pt"
_DEFAULT_MODEL_PATH = _DEFAULT_MODEL_DIR / _DEFAULT_MODEL_NAME

# HuggingFace download URL (DILHTWD, 137 MB)
_HF_MODEL_URL = (
    "https://huggingface.co/DILHTWD/"
    "documentlayoutsegmentation_YOLOv8_ondoclaynet/resolve/main/"
    "yolov8x-doclaynet-epoch64-imgsz640-initiallr1e-4-finallr1e-5.pt"
)


def _download_model(url: str, dest: Path) -> None:
    """Download the YOLO model weights with progress reporting."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    logger.info("Downloading layout model to %s ...", dest)
    logger.info("  URL: %s", url)

    def _progress(block_num, block_size, total_size):
        if total_size > 0:
            pct = min(100, block_num * block_size * 100 // total_size)
            size_mb = total_size / (1024 * 1024)
            print(
                f"\r  Progress: {pct}% of {size_mb:.1f} MB",
                end="",
                flush=True,
            )

    try:
        urllib.request.urlretrieve(url, str(dest), reporthook=_progress)
        print()  # newline after progress
        logger.info("Download complete: %s", dest)
    except Exception as e:
        # Clean up partial download
        if dest.exists():
            dest.unlink()
        raise RuntimeError(f"Failed to download layout model from {url}: {e}") from e


class LayoutDetector:
    """
    Detects document layout regions using a YOLOv8 model trained on
    DocLayNet.

    If the model weights are not found at the expected path, they are
    automatically downloaded from HuggingFace (~137 MB).

    Usage::

        detector = LayoutDetector()
        regions = detector.detect(pil_image)
    """

    def __init__(
        self,
        model_path: Optional[Union[str, Path]] = None,
        device: Optional[str] = None,
    ):
        """
        Load the YOLO model, downloading if necessary.

        Args:
            model_path: Path to ``.pt`` weights.  Defaults to
                        ``models/yolov8x-doclaynet.pt`` in the project root.
            device:     Force a device (``"cpu"``, ``"cuda:0"``, …).
                        ``None`` lets ultralytics auto-select.

        Raises:
            RuntimeError: If the download fails.
        """
        path = Path(model_path) if model_path else _DEFAULT_MODEL_PATH

        if not path.exists():
            # Also check hyphen-style name for backward compat
            alt = path.parent / path.name.replace("_", "-")
            if alt.exists():
                path = alt
            else:
                logger.info("Model not found at %s", path)
                _download_model(_HF_MODEL_URL, _DEFAULT_MODEL_PATH)
                path = _DEFAULT_MODEL_PATH

        self.model = YOLO(str(path), task="detect")
        self.device = device
        self._class_map = self.model.names
        self._validate_classes()

    def detect(
        self,
        image: Image.Image,
        confidence: float = 0.35,
        iou_threshold: float = 0.45,
        image_size: int = 1024,
    ) -> List[LayoutRegion]:
        """
        Run layout detection on a rendered page image.

        Args:
            image:          PIL Image (RGB) of the rendered PDF page.
            confidence:     Minimum confidence to keep a detection.
            iou_threshold:  IoU threshold for NMS.
            image_size:     Inference resolution (longer side).

        Returns:
            List of ``LayoutRegion`` sorted top-to-bottom, left-to-right.
        """
        results = self.model.predict(
            source=image,
            conf=confidence,
            iou=iou_threshold,
            imgsz=image_size,
            device=self.device,
            verbose=False,
        )

        regions: List[LayoutRegion] = []
        if not results or len(results) == 0:
            return regions

        boxes = results[0].boxes
        if boxes is None or len(boxes) == 0:
            return regions

        coords = boxes.xyxy.cpu().numpy()
        confs = boxes.conf.cpu().numpy()
        classes = boxes.cls.cpu().numpy().astype(int)

        for bbox, conf, cls_id in zip(coords, confs, classes):
            label = self._resolve_label(cls_id)
            regions.append(
                LayoutRegion(
                    label=label,
                    confidence=float(conf),
                    bbox=(
                        float(bbox[0]),
                        float(bbox[1]),
                        float(bbox[2]),
                        float(bbox[3]),
                    ),
                )
            )

        regions.sort(key=lambda r: (r.bbox[1], r.bbox[0]))
        return regions

    def detect_and_annotate(
        self,
        image: Image.Image,
        confidence: float = 0.35,
        iou_threshold: float = 0.45,
        image_size: int = 1024,
    ) -> Image.Image:
        """Run detection and return the image with bounding boxes drawn."""
        results = self.model.predict(
            source=image,
            conf=confidence,
            iou=iou_threshold,
            imgsz=image_size,
            device=self.device,
            verbose=False,
        )
        if results:
            annotated = results[0].plot(pil=True)
            return Image.fromarray(annotated[..., ::-1])
        return image

    def _resolve_label(self, cls_id: int) -> LayoutLabel:
        """Map a YOLO class index to a ``LayoutLabel``."""
        if cls_id in DOCLAYNET_INDEX_TO_LABEL:
            return DOCLAYNET_INDEX_TO_LABEL[cls_id]

        name = self._class_map.get(cls_id, "").lower().replace("-", "_")
        for label in LayoutLabel:
            if label.name.lower() == name:
                return label
        return LayoutLabel.UNKNOWN

    def _validate_classes(self) -> None:
        """Log a warning if the model's classes don't match DocLayNet."""
        expected = {
            "caption",
            "footnote",
            "formula",
            "list-item",
            "page-footer",
            "page-header",
            "picture",
            "section-header",
            "table",
            "text",
            "title",
        }
        model_names = {v.lower() for v in self._class_map.values()}
        missing = expected - model_names
        if missing:
            logger.warning("Model is missing expected DocLayNet classes: %s", missing)

    def __repr__(self) -> str:
        n = len(self._class_map)
        return f"LayoutDetector({n} classes, device={self.device})"

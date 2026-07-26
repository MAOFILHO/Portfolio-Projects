"""A self-hosted, no-Azure-cost alternative to AzureVisionAnalyzer --
MobileNet-SSD (Caffe), trained on PASCAL VOC. Sourced from a genuinely
working, MIT-licensed open-source project (see
models/ssd_mobilenet/README.md) rather than trained here. Runs entirely
in-process via OpenCV's DNN module on CPU -- no GPU, no external inference
endpoint, no additional Azure resource, and no per-frame billing.

Selected via the ANALYZER_BACKEND setting (see docs/extending-phase2.md) as
the second implementation of the FrameAnalyzer protocol.

Trade-offs versus AzureVisionAnalyzer, worth knowing before switching:
  - Fixed set of 20 PASCAL VOC classes (see _CLASSES below) -- notably no
    "knife" or "gun". If ALERT_WATCH_TAGS includes either, this backend will
    never match them; it only usefully covers "person", "car", "bicycle",
    "dog", "cat", and the rest of that list.
  - No caption support -- detect() always returns None for caption.
  - Lower accuracy than Azure AI Vision's models, being a much smaller,
    older architecture -- appropriate for a demo/cost comparison, not a
    claim of equivalent detection quality.
"""

from __future__ import annotations

import importlib.resources
from pathlib import Path

import cv2
import numpy as np

from surveil_core.models import Detection

# Index 0 ("background") is the model's no-detection class and is never
# emitted as a Detection.
_CLASSES = [
    "background", "aeroplane", "bicycle", "bird", "boat", "bottle", "bus",
    "car", "cat", "chair", "cow", "diningtable", "dog", "horse", "motorbike",
    "person", "pottedplant", "sheep", "sofa", "train", "tvmonitor",
]

# Matches the source project's preprocessing exactly (people_counter.py):
# resize to a fixed width keeping aspect ratio, then blob the resized frame
# at its own resulting dimensions (not the usual fixed 300x300) with a
# 1/127.5 scale factor and 127.5 mean subtraction.
_RESIZE_WIDTH = 500
_BLOB_SCALE_FACTOR = 1 / 127.5
_BLOB_MEAN = 127.5


def _model_files_dir() -> Path:
    return Path(str(importlib.resources.files("surveil_core") / "models" / "ssd_mobilenet"))


class SsdMobileNetAnalyzer:
    def __init__(self, min_confidence: float = 0.4) -> None:
        model_dir = _model_files_dir()
        prototxt_path = model_dir / "MobileNetSSD_deploy.prototxt"
        model_path = model_dir / "MobileNetSSD_deploy.caffemodel"
        self._net = cv2.dnn.readNetFromCaffe(str(prototxt_path), str(model_path))
        self._min_confidence = min_confidence

    def detect(self, image_bytes: bytes) -> tuple[list[Detection], str | None]:
        image_array = np.frombuffer(image_bytes, dtype=np.uint8)
        image = cv2.imdecode(image_array, cv2.IMREAD_COLOR)
        if image is None:
            return [], None

        (orig_h, orig_w) = image.shape[:2]
        ratio = _RESIZE_WIDTH / float(orig_w)
        resized = cv2.resize(image, (_RESIZE_WIDTH, int(orig_h * ratio)))
        (h, w) = resized.shape[:2]

        blob = cv2.dnn.blobFromImage(resized, _BLOB_SCALE_FACTOR, (w, h), _BLOB_MEAN)
        self._net.setInput(blob)
        raw_detections = self._net.forward()

        detections: list[Detection] = []
        for i in range(raw_detections.shape[2]):
            confidence = float(raw_detections[0, 0, i, 2])
            if confidence < self._min_confidence:
                continue
            class_index = int(raw_detections[0, 0, i, 1])
            if class_index <= 0 or class_index >= len(_CLASSES):
                continue  # 0 is "background"; out-of-range indices are malformed output
            box = raw_detections[0, 0, i, 3:7] * np.array([w, h, w, h])
            (start_x, start_y, end_x, end_y) = box.astype(int)
            detections.append(
                Detection(
                    tag=_CLASSES[class_index],
                    confidence=confidence,
                    bounding_box=(int(start_x), int(start_y), int(end_x - start_x), int(end_y - start_y)),
                )
            )
        return detections, None

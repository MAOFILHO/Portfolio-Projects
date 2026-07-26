"""Pluggable frame-analysis backends.

`FrameAnalyzer` is the seam the Phase-2 project (Custom Vision / YOLOv4
object detection) plugs into. Today only `AzureVisionAnalyzer` exists,
wrapping Azure AI Vision Image Analysis 4.0. Anything implementing
`detect(image_bytes) -> tuple[list[Detection], str | None]` can be swapped
in via the `ANALYZER_BACKEND` setting without touching capture, alerting,
or the deployment pipeline. See docs/extending-phase2.md.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from azure.ai.vision.imageanalysis import ImageAnalysisClient
from azure.ai.vision.imageanalysis.models import VisualFeatures
from azure.core.credentials import AzureKeyCredential, TokenCredential

from surveil_core.models import Detection


@runtime_checkable
class FrameAnalyzer(Protocol):
    """Contract every detection backend must satisfy."""

    def detect(self, image_bytes: bytes) -> tuple[list[Detection], str | None]:
        """Return (detections, caption) for a single JPEG-encoded frame."""
        ...


class AzureVisionAnalyzer:
    """Detects objects/people in a frame using Azure AI Vision Image Analysis 4.0."""

    def __init__(
        self,
        endpoint: str,
        credential: TokenCredential | AzureKeyCredential,
        min_confidence: float = 0.5,
    ) -> None:
        self._client = ImageAnalysisClient(endpoint=endpoint, credential=credential)
        self._min_confidence = min_confidence

    def detect(self, image_bytes: bytes) -> tuple[list[Detection], str | None]:
        # Caption/Dense Captions are only available in a handful of Azure AI
        # Vision regions -- confirmed via Microsoft's current docs that East
        # US (not East US 2) supports it on F0/S0 alike. The Vision resource
        # is deployed to `visionLocation` (default eastus, see main.bicep)
        # specifically so this feature works; requesting it against an
        # unsupported region fails the whole analyze() call with
        # "InvalidRequest: The feature 'Caption' is not supported in this
        # region."
        result = self._client.analyze(
            image_data=image_bytes,
            visual_features=[
                VisualFeatures.OBJECTS,
                VisualFeatures.PEOPLE,
                VisualFeatures.CAPTION,
            ],
        )

        detections: list[Detection] = []

        if result.objects is not None:
            for obj in result.objects.list:
                for tag in obj.tags:
                    if tag.confidence < self._min_confidence:
                        continue
                    box = obj.bounding_box
                    detections.append(
                        Detection(
                            tag=tag.name,
                            confidence=tag.confidence,
                            bounding_box=(box.x, box.y, box.width, box.height),
                        )
                    )

        if result.people is not None:
            for person in result.people.list:
                if person.confidence < self._min_confidence:
                    continue
                box = person.bounding_box
                detections.append(
                    Detection(
                        tag="person",
                        confidence=person.confidence,
                        bounding_box=(box.x, box.y, box.width, box.height),
                    )
                )

        caption = None
        if result.caption is not None and result.caption.confidence >= self._min_confidence:
            caption = result.caption.text

        return detections, caption

    # On-demand, user-triggered analysis (dashboard "Tags" / "Read" / "Smart
    # Crop" buttons) -- separate from detect() above, which is the fixed set
    # of features the alerting pipeline runs on every frame automatically.
    _ON_DEMAND_FEATURES = {
        "tags": VisualFeatures.TAGS,
        "read": VisualFeatures.READ,
        "smartcrops": VisualFeatures.SMART_CROPS,
    }

    def analyze_on_demand(self, image_bytes: bytes, feature_names: list[str]) -> dict:
        """Runs the requested subset of {tags, read, smartcrops} and returns
        JSON-serializable results. Raises KeyError for an unknown feature name.
        """
        features = [self._ON_DEMAND_FEATURES[name] for name in feature_names]
        result = self._client.analyze(image_data=image_bytes, visual_features=features)

        output: dict = {}
        if VisualFeatures.TAGS in features and result.tags is not None:
            output["tags"] = [{"name": t.name, "confidence": t.confidence} for t in result.tags.list]
        if VisualFeatures.READ in features and result.read is not None:
            output["read_lines"] = [
                line.text for block in result.read.blocks for line in block.lines
            ]
        if VisualFeatures.SMART_CROPS in features and result.smart_crops is not None:
            output["smart_crops"] = [
                {
                    "aspect_ratio": crop.aspect_ratio,
                    "bounding_box": [
                        crop.bounding_box.x,
                        crop.bounding_box.y,
                        crop.bounding_box.width,
                        crop.bounding_box.height,
                    ],
                }
                for crop in result.smart_crops.list
            ]
        return output

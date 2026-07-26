# Extending: Phase 2 (custom object detection)

This project was deliberately scoped to fuse two prior prototypes (Blazor webcam capture + Azure infra accelerator) into one working system using Azure AI Vision's pretrained models. A natural next step — not built here — is swapping in a custom-trained detector (e.g. from a "live-video-analytics" / YOLOv4-on-Azure style project), for cases where the generic Vision tags aren't specific enough (e.g. distinguishing a toy gun from a real one, or detecting a domain-specific object Vision doesn't tag).

## The seam: `FrameAnalyzer`

Everything downstream of detection — alert rules, storage, WebSocket fan-out, ACS notifications, the dashboard — depends only on `shared/surveil_core/analyzer.py`'s `FrameAnalyzer` protocol:

```python
class FrameAnalyzer(Protocol):
    def detect(self, image_bytes: bytes) -> tuple[list[Detection], str | None]:
        """Return (detections, caption) for a single JPEG-encoded frame."""
        ...
```

Today, `AzureVisionAnalyzer` is the only implementation, used in both `backend/app/deps.py` and `function/function_app.py`. To add a new backend:

1. Implement `FrameAnalyzer` in `shared/surveil_core/analyzer.py` (or a new module), e.g.:
   ```python
   class CustomVisionAnalyzer:
       def __init__(self, endpoint: str, prediction_key: str, project_id: str, iteration_name: str, min_confidence: float = 0.5): ...
       def detect(self, image_bytes: bytes) -> tuple[list[Detection], str | None]: ...
   ```
   or for a self-hosted YOLOv4 endpoint (e.g. a container running on Container Apps or AKS with GPU), an analyzer that POSTs the frame to that inference endpoint and maps its output to `Detection` objects.

2. Add an `ANALYZER_BACKEND` setting (`azure_vision` | `custom_vision` | `yolo`) to `backend/app/config.py` and `function/function_app.py`'s env reading, and a small factory function that picks the implementation based on it.

3. Add the corresponding Bicep module for whatever the new backend needs (a Custom Vision training+prediction resource pair, or a GPU-backed inference endpoint) — following the same pattern as `infra/modules/vision.bicep`, wired into `infra/main.bicep` behind a `createCustomAnalyzer` bool param (mirroring how the source Foundry project gated its AI Foundry module behind `createFoundryProject`).

4. No changes needed to: capture (`frontend/`), alert-rule evaluation (`alert_rules.py`), storage (`storage.py`), notifications (`notify.py`), the WebSocket fan-out, or the deployment pipeline's stage structure — only `s03_deploy_infra` gains new optional parameters, and `s05`/`s06` build steps are unaffected since they already build whatever's in `backend/`/`function/`.

## If pulling in a third source project

If/when a YOLOv4-on-Azure-style repository is added as a third source, treat it the same way `Video-Agents-Foundry-Solution` was treated here: extract only what's directly reusable (a trained model, a scoring script, a specific Bicep module for GPU inference hosting) rather than importing its full structure, and keep the `FrameAnalyzer` interface as the integration boundary so the rest of this system doesn't need to know or care whether detection is happening via a REST call to Azure AI Vision or a locally-hosted YOLO model.

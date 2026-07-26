"""Azure Function (Python v2 model) — analyzes frames as they land in the
'frames' blob container and raises alerts.

Note: `surveil_core` is not importable here directly from the repo layout —
Azure Functions remote build only sees files inside this function app's own
deployment package. The deploy pipeline's s07_deploy_function step vendors a
copy of shared/surveil_core into this directory (function/surveil_core/,
gitignored) immediately before `func azure functionapp publish`. For local
testing, run `pip install -e ../shared` in this folder's virtualenv instead.
"""

from __future__ import annotations

import logging
import os

import azure.functions as func
import cv2
import numpy as np
from azure.identity import DefaultAzureCredential
from surveil_core import (
    AlertRuleConfig,
    AzureVisionAnalyzer,
    FrameAnalyzer,
    SsdMobileNetAnalyzer,
    SurveillanceEvent,
    AlertMessage,
    evaluate_detections,
)
from surveil_core.alert_rules import compute_severity
from surveil_core.notify import AcsNotifier
from surveil_core.storage import SurveillanceStorage

app = func.FunctionApp()
logger = logging.getLogger("surveil.function")

# SsdMobileNetAnalyzer loads a 23MB model from disk on construction --
# expensive to redo on every invocation. Azure Functions Python reuses the
# worker process across many invocations while warm, so a module-level cache
# is safe here (this file's module scope is per-worker-process, not
# per-invocation) and avoids reloading the model on every frame.
_ssd_analyzer_cache: SsdMobileNetAnalyzer | None = None


def _credential() -> DefaultAzureCredential:
    client_id = os.environ.get("AZURE_CLIENT_ID")
    if client_id:
        return DefaultAzureCredential(managed_identity_client_id=client_id)
    return DefaultAzureCredential()


def _storage() -> SurveillanceStorage:
    account_name = os.environ["STORAGE_ACCOUNT_NAME"]
    account_url = f"https://{account_name}.blob.core.windows.net"
    return SurveillanceStorage(account_url=account_url, credential=_credential())


def _analyzer() -> FrameAnalyzer:
    backend = os.environ.get("ANALYZER_BACKEND", "azure_vision")
    min_confidence = float(os.environ.get("ALERT_MIN_CONFIDENCE", "0.6"))

    if backend == "ssd_mobilenet":
        global _ssd_analyzer_cache
        if _ssd_analyzer_cache is None:
            logger.info("Loading SsdMobileNetAnalyzer (ANALYZER_BACKEND=ssd_mobilenet)")
            _ssd_analyzer_cache = SsdMobileNetAnalyzer(min_confidence=min_confidence)
        return _ssd_analyzer_cache

    endpoint = os.environ["VISION_ENDPOINT"]
    return AzureVisionAnalyzer(endpoint=endpoint, credential=_credential(), min_confidence=min_confidence)


def _severity_map() -> dict[str, str] | None:
    # "tag:severity,tag:severity" -- e.g. "gun:critical,crowd:medium". Empty
    # (default) keeps AlertRuleConfig's built-in DEFAULT_SEVERITY_MAP.
    raw = os.environ.get("ALERT_SEVERITY_MAP", "")
    if not raw.strip():
        return None
    mapping: dict[str, str] = {}
    for pair in raw.split(","):
        if ":" not in pair:
            continue
        tag, _, severity = pair.partition(":")
        tag, severity = tag.strip().lower(), severity.strip().lower()
        if tag and severity:
            mapping[tag] = severity
    return mapping or None


def _restricted_zone() -> tuple[float, float, float, float] | None:
    # "x0,y0,x1,y1" normalized 0.0-1.0 image-fraction coordinates. Empty
    # (default) disables the trespassing rule.
    raw = os.environ.get("ALERT_RESTRICTED_ZONE", "")
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    if len(parts) != 4:
        return None
    try:
        x0, y0, x1, y1 = (float(p) for p in parts)
    except ValueError:
        return None
    return (x0, y0, x1, y1)


def _alert_rule_config() -> AlertRuleConfig:
    watch_tags = [t.strip() for t in os.environ.get("ALERT_WATCH_TAGS", "person").split(",") if t.strip()]
    kwargs: dict = dict(
        watch_tags=watch_tags,
        min_confidence=float(os.environ.get("ALERT_MIN_CONFIDENCE", "0.6")),
        min_count=int(os.environ.get("ALERT_MIN_COUNT", "1")),
        crowd_threshold=int(os.environ.get("ALERT_CROWD_THRESHOLD", "0")),
        restricted_zone=_restricted_zone(),
    )
    severity_map = _severity_map()
    if severity_map is not None:
        kwargs["severity_map"] = severity_map
    return AlertRuleConfig(**kwargs)


def _frame_size(image_bytes: bytes) -> tuple[int, int] | None:
    """Decode just enough of the JPEG to get (width, height) for the
    trespassing zone check. Cheap relative to the analyzer call itself, and
    only decoded once per frame regardless of which analyzer backend runs.
    """
    array = np.frombuffer(image_bytes, dtype=np.uint8)
    image = cv2.imdecode(array, cv2.IMREAD_COLOR)
    if image is None:
        return None
    height, width = image.shape[:2]
    return (width, height)


def _notifier() -> AcsNotifier:
    return AcsNotifier(
        connection_string=os.environ.get("ACS_CONNECTION_STRING") or None,
        sender_email=os.environ.get("ACS_SENDER_EMAIL") or None,
        alert_email_to=os.environ.get("ALERT_EMAIL_TO") or None,
        alert_sms_to=os.environ.get("ALERT_SMS_TO") or None,
        sms_from=os.environ.get("ACS_SMS_FROM") or None,
    )


@app.function_name(name="AnalyzeFrame")
@app.blob_trigger(arg_name="frame", path="frames/{name}", connection="AzureWebJobsStorage")
def analyze_frame(frame: func.InputStream) -> None:
    blob_name = frame.name.split("/", 1)[-1] if "/" in frame.name else frame.name
    camera_id = blob_name.split("/", 1)[0] if "/" in blob_name else "unknown"
    logger.info("Analyzing frame %s (%d bytes) for camera %s", blob_name, frame.length or 0, camera_id)

    image_bytes = frame.read()
    storage = _storage()
    detections, caption = _analyzer().detect(image_bytes)

    config = _alert_rule_config()
    matched_tags = evaluate_detections(detections, config, frame_size=_frame_size(image_bytes))
    is_alert = bool(matched_tags)
    severity = compute_severity(matched_tags, config)

    event = SurveillanceEvent(
        camera_id=camera_id,
        frame_blob_name=blob_name,
        caption=caption,
        detections=detections,
        is_alert=is_alert,
        matched_tags=matched_tags,
        severity=severity,
    )
    storage.save_event(event)
    logger.info(
        "Frame %s analyzed: %d detection(s), alert=%s, matched=%s",
        blob_name, len(detections), is_alert, matched_tags,
    )

    if not is_alert:
        return

    frame_url = storage.upload_annotated_frame(blob_name, image_bytes)
    alert = AlertMessage(
        event_id=event.event_id,
        camera_id=camera_id,
        frame_blob_name=blob_name,
        frame_url=frame_url,
        caption=caption,
        matched_tags=matched_tags,
        severity=severity,
        detections=detections,
    )
    storage.enqueue_alert(alert)
    logger.warning(
        "ALERT [%s]: %s detected on camera %s (event %s)", severity, matched_tags, camera_id, event.event_id
    )

    try:
        _notifier().send_all(alert)
    except Exception:
        logger.exception("Failed to send ACS notification for event %s (alert was still queued for the dashboard)", event.event_id)

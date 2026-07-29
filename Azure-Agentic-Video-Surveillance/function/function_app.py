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

import asyncio
import functools
import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor

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
# surveil_core.agents (specifically its tracing submodule) must be imported
# before `semantic_kernel` -- directly, or transitively via anything else
# below -- gets imported anywhere in this process. See tracing.py's module
# docstring: Semantic Kernel freezes its own OTel-diagnostics env vars into a
# module-level settings singleton the first time it's imported, so importing
# `semantic_kernel` even one line earlier than this silently breaks Langfuse
# tracing for every agent call, with no error anywhere.
from surveil_core.agents import (
    NotificationPolicyAgent,
    TriageAgent,
    agent_span,
    build_kernel,
    flush_langfuse_tracing,
    set_agent_output,
)
from surveil_core.agents.activity_log import log_agent_event
from surveil_core.alert_rules import SEVERITY_ORDER, compute_severity
from surveil_core.notify import AcsNotifier
from surveil_core.storage import SurveillanceStorage
from semantic_kernel import Kernel

app = func.FunctionApp()
logger = logging.getLogger("surveil.function")

# SsdMobileNetAnalyzer loads a 23MB model from disk on construction --
# expensive to redo on every invocation. Azure Functions Python reuses the
# worker process across many invocations while warm, so a module-level cache
# is safe here (this file's module scope is per-worker-process, not
# per-invocation) and avoids reloading the model on every frame.
_ssd_analyzer_cache: SsdMobileNetAnalyzer | None = None

# Same module-level-cache rationale as _ssd_analyzer_cache above: building a
# Kernel (and its AzureChatCompletion service) per-invocation would be
# wasteful across a warm worker process.
_kernel_cache: Kernel | None = None

# Confirmed live: ACS email hit its Azure-managed domain's rate limit
# (TooManyRequests) after a burst of near-duplicate "person" detections from
# a looping test video -- every one of those tried to notify. This cache
# (camera_id, sorted matched_tags) -> last-notified timestamp, kept on the
# same warm-worker-process basis as the caches above, throttles repeat
# notifications for the same camera+threat-type within the cooldown window.
# It never touches whether the event/alert itself is recorded -- only
# whether ACS email/SMS gets attempted -- and critical severity always
# bypasses it, same non-negotiable-guardrail spirit as the Triage Agent's
# escalate-only-never-suppress rule.
_NOTIFICATION_COOLDOWN_SECONDS = float(os.environ.get("NOTIFICATION_COOLDOWN_SECONDS", "60"))
_last_notified_cache: dict[tuple[str, tuple[str, ...]], float] = {}


def _within_notification_cooldown(camera_id: str, matched_tags: list[str]) -> bool:
    key = (camera_id, tuple(sorted(matched_tags)))
    last_notified = _last_notified_cache.get(key)
    return last_notified is not None and (time.monotonic() - last_notified) < _NOTIFICATION_COOLDOWN_SECONDS


def _mark_notified(camera_id: str, matched_tags: list[str]) -> None:
    _last_notified_cache[(camera_id, tuple(sorted(matched_tags)))] = time.monotonic()


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


def _agents_enabled() -> bool:
    # If OPENAI_ENDPOINT isn't set (e.g. local dev, or a partial rollout
    # before the Azure OpenAI resource exists), skip agent construction
    # entirely rather than attempting-then-catching an exception on every
    # single frame -- keeps the no-agents path exactly as fast and simple as
    # it was before this feature existed.
    return bool(os.environ.get("OPENAI_ENDPOINT"))


def _kernel() -> Kernel:
    global _kernel_cache
    if _kernel_cache is None:
        endpoint = os.environ["OPENAI_ENDPOINT"]
        deployment_name = os.environ.get("OPENAI_CHAT_DEPLOYMENT", "chat")
        _kernel_cache = build_kernel(endpoint=endpoint, deployment_name=deployment_name, credential=_credential())
    return _kernel_cache


def _triage_agent() -> TriageAgent:
    return TriageAgent(_kernel())


def _notification_policy_agent() -> NotificationPolicyAgent:
    return NotificationPolicyAgent(_kernel())


def _is_higher_severity(candidate: str | None, current: str | None) -> bool:
    """True if `candidate` ranks strictly higher than `current` per
    SEVERITY_ORDER (index 0 = highest, e.g. "critical"). A `current` that
    isn't a recognized severity is treated as lower than every real one.
    """
    if not candidate or candidate not in SEVERITY_ORDER:
        return False
    if not current or current not in SEVERITY_ORDER:
        return True
    return SEVERITY_ORDER.index(candidate) < SEVERITY_ORDER.index(current)


# A rate-limited (429) Azure OpenAI call can carry a `Retry-After` header of
# thousands of seconds; the OpenAI SDK's built-in retry logic can honor that
# and sleep accordingly, which -- without a hard backstop here -- silently
# blocks the whole Function invocation well past its own execution timeout
# (5 min default / 10 min hard cap on Consumption). This is a real failure
# mode confirmed live ("Timeout value of 00:05:00 was exceeded by function:
# Functions.AnalyzeFrame"), not a hypothetical one: a plain try/except does
# NOT protect against a hang, only against a raised exception. Every agent
# call below must go through asyncio.wait_for so a stuck call is cancelled
# and treated exactly like any other agent failure -- fast fallback to the
# deterministic rule-engine result, never a blocked invocation.
_AGENT_CALL_TIMEOUT_SECONDS = 20.0

# Same rationale as _AGENT_CALL_TIMEOUT_SECONDS, but for the plain (non-agent)
# Vision/Storage/ACS SDK calls in this function. asyncio.to_thread() alone
# only stops a blocking call from freezing OTHER concurrent invocations'
# shared event loop -- it does nothing to bound how long *this* invocation
# waits on it. Confirmed live: a Vision detect() call hung indefinitely under
# load (no agent involved at all) and separately an ACS send hit
# TooManyRequests (429) and hung -- both silently ran out the full 5-minute
# function timeout before this guardrail existed. Every blocking call must
# go through _run_blocking() so a stuck call raises promptly instead of
# hanging; the blob trigger's own retry policy handles a failed invocation,
# which is far better than one holding a worker slot for 5 minutes.
_IO_CALL_TIMEOUT_SECONDS = 60.0

# asyncio.to_thread() runs on the event loop's DEFAULT executor, which sizes
# itself to min(32, os.cpu_count() + 4). On this Function App's Consumption
# plan (1 vCPU), that default is only 5 threads total for the whole worker
# process -- confirmed live: Vision's own telemetry showed 100% success and
# sub-second latency for every call it actually received, while our
# invocations still timed out at the full _IO_CALL_TIMEOUT_SECONDS. Each
# invocation makes several sequential blocking calls (detect, save_event,
# upload_annotated_frame, enqueue_alert, notify), so a handful of concurrent
# invocations alone exhausts that 5-thread pool -- calls were queuing for the
# entire timeout waiting for a free thread, never actually reaching the
# network. A dedicated, generously-sized pool fixes the real bottleneck
# instead of just tolerating it with a longer timeout.
_BLOCKING_CALL_EXECUTOR = ThreadPoolExecutor(max_workers=64, thread_name_prefix="surveil-io")


async def _run_blocking(func, *args, **kwargs):
    loop = asyncio.get_running_loop()
    call = functools.partial(func, *args, **kwargs)
    return await asyncio.wait_for(loop.run_in_executor(_BLOCKING_CALL_EXECUTOR, call), timeout=_IO_CALL_TIMEOUT_SECONDS)


@app.function_name(name="AnalyzeFrame")
@app.blob_trigger(arg_name="frame", path="frames/{name}", connection="AzureWebJobsStorage", source="EventGrid")
async def analyze_frame(frame: func.InputStream) -> None:
    # Azure Functions Consumption invocations are short-lived -- the worker
    # process can be reused or torn down well before Langfuse's
    # BatchSpanProcessor's own periodic export timer would fire on its own,
    # silently dropping this invocation's agent spans (confirmed live: no
    # traces appeared in Langfuse despite live triage/notification agent
    # calls succeeding, until this flush was added -- see
    # docs/troubleshooting.md #20). `finally` guarantees this runs on every
    # return path and on any unhandled exception, not just the happy path.
    try:
        await _analyze_frame_impl(frame)
    finally:
        flush_langfuse_tracing()


async def _analyze_frame_impl(frame: func.InputStream) -> None:
    blob_name = frame.name.split("/", 1)[-1] if "/" in frame.name else frame.name
    camera_id = blob_name.split("/", 1)[0] if "/" in blob_name else "unknown"
    logger.info("Analyzing frame %s (%d bytes) for camera %s", blob_name, frame.length or 0, camera_id)

    image_bytes = frame.read()
    storage = _storage()
    detections, caption = await _run_blocking(_analyzer().detect, image_bytes)

    config = _alert_rule_config()
    matched_tags = evaluate_detections(detections, config, frame_size=_frame_size(image_bytes))
    is_alert = bool(matched_tags)
    severity = compute_severity(matched_tags, config)

    # Triage Agent: may only escalate severity upward, and only ever gets a
    # chance to run when the rule engine's own severity isn't already
    # "critical" -- there is no code path from here that can reach a
    # critical rule-engine classification and change it. On any failure
    # (including the agent recommending suppression, which is logged but
    # never auto-applied in v1), `final_severity` stays exactly what the
    # deterministic rule engine produced.
    final_severity = severity
    if is_alert and severity != "critical" and _agents_enabled():
        with agent_span(
            "triage-detection",
            input={"caption": caption, "matched_tags": matched_tags, "rule_severity": severity},
            metadata={"camera_id": camera_id, "frame_blob_name": blob_name},
            tags=["triage_agent"],
        ) as span:
            try:
                triage_result = await asyncio.wait_for(
                    _triage_agent().triage(caption=caption, matched_tags=matched_tags, rule_severity=severity),
                    timeout=_AGENT_CALL_TIMEOUT_SECONDS,
                )
                if triage_result.escalate and _is_higher_severity(triage_result.escalated_severity, severity):
                    final_severity = triage_result.escalated_severity
                if triage_result.suppress_recommended:
                    await _run_blocking(
                        storage.log_audit_event,
                        actor="triage_agent",
                        action="suppress_recommended_not_applied",
                        details=f"tags={matched_tags} reason={triage_result.suppress_reason}",
                    )
                set_agent_output(span, {
                    "escalate": triage_result.escalate,
                    "escalated_severity": triage_result.escalated_severity,
                    "suppress_recommended": triage_result.suppress_recommended,
                    "final_severity": final_severity,
                })
            except Exception:
                logger.exception("Triage agent call failed for frame %s -- falling back to rule-engine severity", blob_name)
                final_severity = severity
                set_agent_output(span, {"error": "triage_agent_call_failed", "final_severity": final_severity})
        log_agent_event(
            logger, "Orchestrator", "triage_decision",
            frame=blob_name, rule_severity=severity, final_severity=final_severity,
        )

    event = SurveillanceEvent(
        camera_id=camera_id,
        frame_blob_name=blob_name,
        caption=caption,
        detections=detections,
        is_alert=is_alert,
        matched_tags=matched_tags,
        severity=final_severity,
    )
    await _run_blocking(storage.save_event, event)
    logger.info(
        "Frame %s analyzed: %d detection(s), alert=%s, matched=%s",
        blob_name, len(detections), is_alert, matched_tags,
    )

    if not is_alert:
        return

    frame_url = await _run_blocking(storage.upload_annotated_frame, blob_name, image_bytes)
    alert = AlertMessage(
        event_id=event.event_id,
        camera_id=camera_id,
        frame_blob_name=blob_name,
        frame_url=frame_url,
        caption=caption,
        matched_tags=matched_tags,
        severity=final_severity,
        detections=detections,
    )
    await _run_blocking(storage.enqueue_alert, alert)
    logger.warning(
        "ALERT [%s]: %s detected on camera %s (event %s)", final_severity, matched_tags, camera_id, event.event_id
    )

    # Cooldown never applies to critical severity -- same non-negotiable
    # guardrail spirit as the Triage Agent's escalate-only-never-suppress
    # rule. The event/alert itself is already recorded above regardless;
    # this only ever skips the ACS email/SMS attempt for a throttled repeat.
    if final_severity != "critical" and _within_notification_cooldown(camera_id, matched_tags):
        logger.info(
            "Skipping notification for event %s -- camera %s already notified for %s within the last %.0fs",
            event.event_id, camera_id, matched_tags, _NOTIFICATION_COOLDOWN_SECONDS,
        )
        return
    _mark_notified(camera_id, matched_tags)

    # Notification Policy Agent: only narrows/frames delivery channels --
    # `channels=None` is the sentinel for "use send_all() unchanged", which
    # is exactly today's behavior whenever agents are disabled or the call
    # fails.
    channels: list[str] | None = None
    if _agents_enabled():
        with agent_span(
            "notification-policy-decide",
            input={"severity": final_severity, "matched_tags": matched_tags, "camera_id": camera_id},
            metadata={"camera_id": camera_id, "event_id": event.event_id},
            tags=["notification_policy_agent"],
        ) as span:
            try:
                decision = await asyncio.wait_for(
                    _notification_policy_agent().decide(alert), timeout=_AGENT_CALL_TIMEOUT_SECONDS
                )
                channels = decision.channels
                set_agent_output(span, {"channels": channels, "reasoning": decision.reasoning})
            except Exception:
                logger.exception(
                    "Notification policy agent call failed for event %s -- falling back to all channels", event.event_id
                )
                channels = None
                set_agent_output(span, {"error": "notification_policy_agent_call_failed", "channels": ["email", "sms"]})
        log_agent_event(
            logger, "Orchestrator", "notification_decision",
            event_id=event.event_id, channels=channels or ["email", "sms"],
        )

    try:
        if channels is None:
            await _run_blocking(_notifier().send_all, alert)
        else:
            await _run_blocking(_notifier().send_selected, alert, channels)
    except Exception:
        logger.exception("Failed to send ACS notification for event %s (alert was still queued for the dashboard)", event.event_id)

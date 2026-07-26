"""Alert-rule evaluation: decides whether a set of detections should raise an alert.

Kept as a pure function (no I/O) so it is trivially unit-testable and shared
verbatim between the FastAPI backend (for local/dev evaluation) and the
Azure Function analysis worker (the production evaluation path).
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from surveil_core.models import Detection

# Severity ranking, highest first. Only tags that this system can actually
# produce today are mapped by default -- "critical" categories like fire,
# smoke, or assault (requested by the user) are NOT included because no
# detector wired into this project (Azure Vision Objects/People, or the
# self-hosted SSD-MobileNet 20-class VOC model) can currently distinguish
# them; adding them honestly requires custom-trained detection, not a config
# change. See docs/extending-phase2.md for what a future ML backend swap
# would need to provide. This map is fully overridable via
# ALERT_SEVERITY_MAP so a future backend can extend it without code changes.
SEVERITY_ORDER = ["critical", "high", "medium", "low"]

DEFAULT_SEVERITY_MAP: dict[str, str] = {
    "gun": "critical",
    "knife": "critical",
    "weapon": "critical",
    "trespassing": "high",
    "crowd": "medium",
    "person": "low",
}


class AlertRuleConfig(BaseModel):
    """Mirrors the ALERT_* settings in .env."""

    watch_tags: list[str] = Field(default_factory=lambda: ["person"])
    min_confidence: float = 0.6
    min_count: int = 1

    # Severity levels -- tag (lowercased) -> "critical" | "high" | "medium" | "low".
    # Tags not present here fall back to "low" once matched (an alert fired,
    # so it is never "no severity", just the lowest tier by default).
    severity_map: dict[str, str] = Field(default_factory=lambda: dict(DEFAULT_SEVERITY_MAP))

    # Crowd rule: synthesizes a "crowd" pseudo-tag (in addition to any
    # per-object watch-tag matches) when at least this many "person"
    # detections appear in one frame. 0 disables the rule.
    crowd_threshold: int = 0

    # Trespassing / perimeter-intrusion rule: a single global restricted
    # zone, normalized to (x0, y0, x1, y1) in 0.0-1.0 image-fraction
    # coordinates so it is resolution-independent. Synthesizes a
    # "trespassing" pseudo-tag when a person detection's center falls inside
    # it. None (default) disables the rule. Per-camera zones would need a
    # config UI and are a natural follow-up, not built here.
    restricted_zone: tuple[float, float, float, float] | None = None

    def normalized_watch_tags(self) -> set[str]:
        return {tag.strip().lower() for tag in self.watch_tags if tag.strip()}


def _zone_hit(box: tuple[int, int, int, int], frame_size: tuple[int, int], zone: tuple[float, float, float, float]) -> bool:
    x, y, w, h = box
    frame_w, frame_h = frame_size
    if frame_w <= 0 or frame_h <= 0:
        return False
    cx = (x + w / 2) / frame_w
    cy = (y + h / 2) / frame_h
    x0, y0, x1, y1 = zone
    return x0 <= cx <= x1 and y0 <= cy <= y1


def evaluate_detections(
    detections: list[Detection],
    config: AlertRuleConfig,
    frame_size: tuple[int, int] | None = None,
) -> list[str]:
    """Return the sorted list of matched watch-tags, or [] if no alert should fire.

    A tag matches when at least `min_count` detections of that tag are present
    at or above `min_confidence`. An empty `watch_tags` list means "alert on
    any detected tag" (useful for a maximally-sensitive demo run).

    Also evaluates two derived (synthesized) tags on top of straight
    watch-tag matching, independent of `watch_tags`/`min_count`:
    - "crowd": `crowd_threshold` or more above-confidence "person" detections.
    - "trespassing": a "person" detection centered inside `restricted_zone`
      (requires `frame_size`; silently skipped without it).
    """
    watch_tags = config.normalized_watch_tags()
    counts: dict[str, int] = {}
    person_count = 0
    trespass = False

    for detection in detections:
        if detection.confidence < config.min_confidence:
            continue
        tag = detection.tag.strip().lower()

        if tag == "person":
            person_count += 1
            if (
                config.restricted_zone is not None
                and frame_size is not None
                and detection.bounding_box is not None
                and _zone_hit(detection.bounding_box, frame_size, config.restricted_zone)
            ):
                trespass = True

        if watch_tags and tag not in watch_tags:
            continue
        counts[tag] = counts.get(tag, 0) + 1

    matched = {tag for tag, count in counts.items() if count >= config.min_count}

    if config.crowd_threshold > 0 and person_count >= config.crowd_threshold:
        matched.add("crowd")
    if trespass:
        matched.add("trespassing")

    return sorted(matched)


def compute_severity(matched_tags: list[str], config: AlertRuleConfig) -> str | None:
    """Return the highest severity among matched tags, or None if no tags matched."""
    if not matched_tags:
        return None
    severities = {config.severity_map.get(tag, "low") for tag in matched_tags}
    for level in SEVERITY_ORDER:
        if level in severities:
            return level
    return "low"

from surveil_core.alert_rules import AlertRuleConfig, compute_severity, evaluate_detections
from surveil_core.models import Detection


def test_no_detections_no_alert():
    assert evaluate_detections([], AlertRuleConfig()) == []


def test_matching_tag_above_confidence_triggers_alert():
    detections = [Detection(tag="person", confidence=0.8)]
    config = AlertRuleConfig(watch_tags=["person"], min_confidence=0.6, min_count=1)
    assert evaluate_detections(detections, config) == ["person"]


def test_below_confidence_does_not_trigger():
    detections = [Detection(tag="person", confidence=0.3)]
    config = AlertRuleConfig(watch_tags=["person"], min_confidence=0.6, min_count=1)
    assert evaluate_detections(detections, config) == []


def test_unwatched_tag_ignored():
    detections = [Detection(tag="dog", confidence=0.99)]
    config = AlertRuleConfig(watch_tags=["person"], min_confidence=0.6, min_count=1)
    assert evaluate_detections(detections, config) == []


def test_min_count_requires_multiple_matches():
    detections = [Detection(tag="person", confidence=0.9)]
    config = AlertRuleConfig(watch_tags=["person"], min_confidence=0.6, min_count=2)
    assert evaluate_detections(detections, config) == []

    detections_two = [Detection(tag="person", confidence=0.9), Detection(tag="person", confidence=0.7)]
    assert evaluate_detections(detections_two, config) == ["person"]


def test_empty_watch_tags_matches_anything():
    detections = [Detection(tag="bicycle", confidence=0.7)]
    config = AlertRuleConfig(watch_tags=[], min_confidence=0.5, min_count=1)
    assert evaluate_detections(detections, config) == ["bicycle"]


def test_case_insensitive_tag_matching():
    detections = [Detection(tag="Person", confidence=0.9)]
    config = AlertRuleConfig(watch_tags=["PERSON"], min_confidence=0.6, min_count=1)
    assert evaluate_detections(detections, config) == ["person"]


def test_multiple_matched_tags_sorted():
    detections = [
        Detection(tag="knife", confidence=0.9),
        Detection(tag="person", confidence=0.9),
    ]
    config = AlertRuleConfig(watch_tags=["person", "knife"], min_confidence=0.5, min_count=1)
    assert evaluate_detections(detections, config) == ["knife", "person"]


def test_crowd_threshold_synthesizes_crowd_tag():
    detections = [Detection(tag="person", confidence=0.9) for _ in range(4)]
    config = AlertRuleConfig(watch_tags=["person"], min_confidence=0.5, min_count=1, crowd_threshold=4)
    assert evaluate_detections(detections, config) == ["crowd", "person"]


def test_crowd_threshold_not_met_no_crowd_tag():
    detections = [Detection(tag="person", confidence=0.9) for _ in range(3)]
    config = AlertRuleConfig(watch_tags=["person"], min_confidence=0.5, min_count=1, crowd_threshold=4)
    assert evaluate_detections(detections, config) == ["person"]


def test_crowd_threshold_disabled_by_default():
    detections = [Detection(tag="person", confidence=0.9) for _ in range(50)]
    config = AlertRuleConfig(watch_tags=["person"], min_confidence=0.5, min_count=1)
    assert "crowd" not in evaluate_detections(detections, config)


def test_restricted_zone_hit_synthesizes_trespassing_tag():
    # Frame is 100x100; box center at (50, 50) -> normalized (0.5, 0.5),
    # inside the zone (0.0, 0.0)-(1.0, 1.0).
    detections = [Detection(tag="person", confidence=0.9, bounding_box=(40, 40, 20, 20))]
    config = AlertRuleConfig(
        watch_tags=["person"], min_confidence=0.5, min_count=1, restricted_zone=(0.0, 0.0, 1.0, 1.0)
    )
    assert evaluate_detections(detections, config, frame_size=(100, 100)) == ["person", "trespassing"]


def test_restricted_zone_miss_no_trespassing_tag():
    # Box center at (5, 5) -> normalized (0.05, 0.05), outside the zone.
    detections = [Detection(tag="person", confidence=0.9, bounding_box=(0, 0, 10, 10))]
    config = AlertRuleConfig(
        watch_tags=["person"], min_confidence=0.5, min_count=1, restricted_zone=(0.5, 0.5, 1.0, 1.0)
    )
    assert evaluate_detections(detections, config, frame_size=(100, 100)) == ["person"]


def test_restricted_zone_without_frame_size_is_skipped():
    detections = [Detection(tag="person", confidence=0.9, bounding_box=(40, 40, 20, 20))]
    config = AlertRuleConfig(
        watch_tags=["person"], min_confidence=0.5, min_count=1, restricted_zone=(0.0, 0.0, 1.0, 1.0)
    )
    assert evaluate_detections(detections, config) == ["person"]


def test_compute_severity_highest_wins():
    config = AlertRuleConfig()
    assert compute_severity(["person", "gun"], config) == "critical"
    assert compute_severity(["crowd"], config) == "medium"
    assert compute_severity(["person"], config) == "low"


def test_compute_severity_no_match_is_none():
    config = AlertRuleConfig()
    assert compute_severity([], config) is None


def test_compute_severity_unmapped_tag_defaults_to_low():
    config = AlertRuleConfig()
    assert compute_severity(["bicycle"], config) == "low"


def test_compute_severity_custom_map_override():
    config = AlertRuleConfig(severity_map={"dog": "high"})
    assert compute_severity(["dog"], config) == "high"

from __future__ import annotations

from pathlib import Path

import pytest
from surveil_core.ssd_analyzer import SsdMobileNetAnalyzer

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "person_test_frame.jpg"


@pytest.fixture(scope="module")
def analyzer() -> SsdMobileNetAnalyzer:
    # Loads the real bundled model -- this is a genuine functional test, not
    # a mock, since the whole point of this analyzer is that it needs no
    # external service to run.
    return SsdMobileNetAnalyzer(min_confidence=0.4)


def test_detects_person_in_real_fixture(analyzer: SsdMobileNetAnalyzer) -> None:
    image_bytes = FIXTURE_PATH.read_bytes()

    detections, caption = analyzer.detect(image_bytes)

    assert caption is None
    tags = [d.tag for d in detections]
    assert "person" in tags
    for d in detections:
        assert 0.0 <= d.confidence <= 1.0
        assert d.bounding_box is not None
        assert len(d.bounding_box) == 4


def test_returns_empty_for_undecodable_bytes(analyzer: SsdMobileNetAnalyzer) -> None:
    detections, caption = analyzer.detect(b"not a real image")

    assert detections == []
    assert caption is None


def test_high_threshold_filters_everything_out(analyzer: SsdMobileNetAnalyzer) -> None:
    strict_analyzer = SsdMobileNetAnalyzer(min_confidence=0.999)
    image_bytes = FIXTURE_PATH.read_bytes()

    detections, _ = strict_analyzer.detect(image_bytes)

    assert detections == []

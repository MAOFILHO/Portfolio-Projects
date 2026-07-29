from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from surveil_core.analyzer import AzureVisionAnalyzer, FrameAnalyzer


def _fake_result(objects=None, people=None, caption=None):
    return SimpleNamespace(objects=objects, people=people, caption=caption)


def _box(x=0, y=0, w=10, h=10):
    return SimpleNamespace(x=x, y=y, width=w, height=h)


def test_frame_analyzer_protocol_is_satisfied_by_azure_vision_analyzer():
    with patch("surveil_core.analyzer.ImageAnalysisClient"):
        analyzer = AzureVisionAnalyzer(endpoint="https://example.cognitiveservices.azure.com/", credential=MagicMock())
    assert isinstance(analyzer, FrameAnalyzer)


def test_detect_extracts_object_tags_above_confidence():
    with patch("surveil_core.analyzer.ImageAnalysisClient") as mock_client_cls:
        mock_client = mock_client_cls.return_value
        obj = SimpleNamespace(
            bounding_box=_box(),
            tags=[SimpleNamespace(name="person", confidence=0.9), SimpleNamespace(name="chair", confidence=0.2)],
        )
        mock_client.analyze.return_value = _fake_result(
            objects=SimpleNamespace(list=[obj]),
            people=None,
            caption=None,
        )
        analyzer = AzureVisionAnalyzer(endpoint="https://example/", credential=MagicMock(), min_confidence=0.5)
        detections, caption = analyzer.detect(b"fake-jpeg-bytes")

    tags = {d.tag for d in detections}
    assert tags == {"person"}
    assert caption is None


def test_detect_extracts_people_as_person_tag():
    with patch("surveil_core.analyzer.ImageAnalysisClient") as mock_client_cls:
        mock_client = mock_client_cls.return_value
        person = SimpleNamespace(confidence=0.85, bounding_box=_box())
        mock_client.analyze.return_value = _fake_result(
            objects=None,
            people=SimpleNamespace(list=[person]),
            caption=None,
        )
        analyzer = AzureVisionAnalyzer(endpoint="https://example/", credential=MagicMock(), min_confidence=0.5)
        detections, _ = analyzer.detect(b"fake-jpeg-bytes")

    assert len(detections) == 1
    assert detections[0].tag == "person"
    assert detections[0].confidence == 0.85


def test_detect_returns_caption_above_threshold():
    with patch("surveil_core.analyzer.ImageAnalysisClient") as mock_client_cls:
        mock_client = mock_client_cls.return_value
        mock_client.analyze.return_value = _fake_result(
            objects=None, people=None,
            caption=SimpleNamespace(text="a person standing", confidence=0.8),
        )
        analyzer = AzureVisionAnalyzer(endpoint="https://example/", credential=MagicMock(), min_confidence=0.5)
        _, caption = analyzer.detect(b"fake-jpeg-bytes")

    assert caption == "a person standing"


def test_detect_suppresses_low_confidence_caption():
    with patch("surveil_core.analyzer.ImageAnalysisClient") as mock_client_cls:
        mock_client = mock_client_cls.return_value
        mock_client.analyze.return_value = _fake_result(
            objects=None, people=None,
            caption=SimpleNamespace(text="unsure caption", confidence=0.1),
        )
        analyzer = AzureVisionAnalyzer(endpoint="https://example/", credential=MagicMock(), min_confidence=0.5)
        _, caption = analyzer.detect(b"fake-jpeg-bytes")

    assert caption is None

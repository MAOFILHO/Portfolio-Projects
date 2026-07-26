"""Regression tests for the frame-upload naming/content-type logic.

Guards against the bug found in the original Ai-Detect-Video-Alert app,
where JPEG-encoded frames were uploaded with a `.png` blob name and no
content-type — see docs/architecture.md "Improvements over the originals".
"""

from app.routes.frames import _blob_name


def test_blob_name_has_camera_prefix_and_jpg_extension():
    name = _blob_name("front-door")
    assert name.startswith("front-door/")
    assert name.endswith(".jpg")


def test_blob_name_is_unique_across_calls():
    names = {_blob_name("cam1") for _ in range(20)}
    assert len(names) == 20

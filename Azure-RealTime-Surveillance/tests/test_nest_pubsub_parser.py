from __future__ import annotations

import json

from pubsub_parser import parse_camera_events


def _message(events: dict) -> bytes:
    return json.dumps(
        {
            "resourceUpdate": {
                "name": "enterprises/proj-1/devices/device-1",
                "events": events,
            }
        }
    ).encode()


def test_parses_single_motion_event():
    data = _message({"sdm.devices.events.CameraMotion.Motion": {"eventId": "evt-1"}})
    events = parse_camera_events(data)
    assert len(events) == 1
    assert events[0].event_type == "sdm.devices.events.CameraMotion.Motion"
    assert events[0].event_id == "evt-1"
    assert events[0].device_name == "enterprises/proj-1/devices/device-1"


def test_parses_multiple_simultaneous_events():
    data = _message(
        {
            "sdm.devices.events.CameraMotion.Motion": {"eventId": "evt-1"},
            "sdm.devices.events.CameraPerson.Person": {"eventId": "evt-2"},
        }
    )
    events = parse_camera_events(data)
    assert {e.event_type for e in events} == {
        "sdm.devices.events.CameraMotion.Motion",
        "sdm.devices.events.CameraPerson.Person",
    }


def test_returns_empty_list_when_no_resource_update():
    data = json.dumps({"userId": "abc"}).encode()
    assert parse_camera_events(data) == []


def test_skips_events_missing_event_id_and_preview_url():
    data = _message({"sdm.devices.events.CameraMotion.Motion": {}})
    assert parse_camera_events(data) == []


def test_parses_clip_preview_event_by_preview_url():
    data = _message(
        {
            "sdm.devices.events.CameraClipPreview.ClipPreview": {
                "eventSessionId": "sess-1",
                "previewUrl": "https://example.com/clip.gif",
            }
        }
    )
    events = parse_camera_events(data)
    assert len(events) == 1
    assert events[0].event_id is None
    assert events[0].preview_url == "https://example.com/clip.gif"


def test_parses_person_and_clip_preview_from_same_message():
    data = _message(
        {
            "sdm.devices.events.CameraPerson.Person": {"eventId": "evt-1"},
            "sdm.devices.events.CameraClipPreview.ClipPreview": {"previewUrl": "https://example.com/clip.gif"},
        }
    )
    events = parse_camera_events(data)
    assert len(events) == 2
    by_type = {e.event_type: e for e in events}
    assert by_type["sdm.devices.events.CameraPerson.Person"].preview_url is None
    assert by_type["sdm.devices.events.CameraClipPreview.ClipPreview"].event_id is None

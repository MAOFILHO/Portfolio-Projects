from __future__ import annotations

from webrtc_capture import _patch_missing_candidate_foundations


def test_inserts_foundation_before_component_and_transport():
    line = "a=candidate: 1 udp 2113932031 74.125.247.229 19305 typ host generation 0"
    patched = _patch_missing_candidate_foundations(line)
    assert patched == "a=candidate:1 1 udp 2113932031 74.125.247.229 19305 typ host generation 0"


def test_assigns_unique_foundation_per_candidate_line():
    sdp = (
        "a=candidate: 1 udp 2113932031 74.125.247.229 19305 typ host generation 0\n"
        "a=candidate: 1 tcp 2113932030 74.125.247.134 19305 typ host tcptype passive generation 0\n"
    )
    patched = _patch_missing_candidate_foundations(sdp)
    lines = patched.splitlines()
    assert lines[0].startswith("a=candidate:1 1 udp")
    assert lines[1].startswith("a=candidate:2 1 tcp")


def test_leaves_conformant_candidate_lines_unaffected():
    # A line that already has a foundation token shouldn't match/change.
    line = "a=candidate:1 1 udp 2113932031 74.125.247.229 19305 typ host generation 0"
    assert _patch_missing_candidate_foundations(line) == line


def test_leaves_non_candidate_lines_unaffected():
    sdp = "v=0\r\no=- 0 2 IN IP4 127.0.0.1\r\ns=-\r\n"
    assert _patch_missing_candidate_foundations(sdp) == sdp

"""ACS media-frame shapes.

The one place that knows how an ACS bidirectional media frame is spelled. Extracted from the
Phase 1 relay's two inner loops unchanged (Phase 2.1 restructure, issue #17) so the verified
protocol facts live in one module rather than inline in the relay.

Inbound keys are lowercase ("kind"/"audioData"/"data"), outbound keys are capitalized
("Kind"/"AudioData"/"Data") -- a real, verified ACS asymmetry, not a bug: docs/PLAN.md's "Key
protocol facts (verified)" states it explicitly, and the Phase 0 app used exactly this casing
on both sides in the code that answered and echoed all 3 real test calls.

The FakeTransport that lets a whole call run in CI with no Azure (docs/PLAN.md Phase 2) is
issue #18's deliverable and lands beside this module.
"""
import json

DTMF = "dtmf"
AUDIO = "audio"
OTHER = "other"


def classify_inbound(raw_text):
    """Returns (kind, audio_payload) for one inbound ACS frame.

    `kind` is DTMF, AUDIO, or OTHER. `audio_payload` is the base64 PCM string for AUDIO and
    None otherwise -- deliberately None for DTMF: the tone value must never leave this
    function (B2, PIN confidentiality), so there is nothing for a caller to accidentally log
    or forward.
    """
    msg = json.loads(raw_text)
    kind = msg.get("kind")
    if kind == "DtmfData":
        return DTMF, None
    if kind == "AudioData":
        return AUDIO, msg["audioData"]["data"]
    return OTHER, None


def outbound_audio_frame(b64_audio):
    """Builds one outbound ACS audio frame -- capitalized keys, per the asymmetry above."""
    return json.dumps({"Kind": "AudioData", "AudioData": {"Data": b64_audio}})

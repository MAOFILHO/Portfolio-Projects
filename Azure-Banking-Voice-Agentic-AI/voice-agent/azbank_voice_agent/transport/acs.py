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
    """Returns (kind, payload) for one inbound ACS frame.

    `kind` is DTMF, AUDIO, or OTHER. `payload` is the base64 PCM string for AUDIO, the keyed
    digit for DTMF, and None otherwise.

    **This function used to return None for a DTMF tone on purpose**, so that the tone value could
    not leave it -- which was the right shape while nothing consumed one. Phase 4 gives the digit a
    consumer (the call's authenticator), and the alternative to returning it here was a second
    function parsing the same frame a second time. One classifier and one parse per frame is the
    smaller surface: B2 is kept by what the *relay* does with the value, which is hand it straight
    to the authenticator and log neither it nor its length.
    """
    msg = json.loads(raw_text)
    kind = msg.get("kind")
    if kind == "DtmfData":
        # Defensively dug out rather than indexed. A malformed DTMF frame must not raise on the
        # inbound relay task, which would end the call: the authenticator ignores a key it does
        # not recognise, and None is one of those.
        return DTMF, (msg.get("dtmfData") or {}).get("data")
    if kind == "AudioData":
        return AUDIO, msg["audioData"]["data"]
    return OTHER, None


def outbound_audio_frame(b64_audio):
    """Builds one outbound ACS audio frame -- capitalized keys, per the asymmetry above."""
    return json.dumps({"Kind": "AudioData", "AudioData": {"Data": b64_audio}})

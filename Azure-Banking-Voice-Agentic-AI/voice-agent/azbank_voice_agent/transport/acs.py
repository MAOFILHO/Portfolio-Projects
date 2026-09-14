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

#: The two keys the keypad gives meaning to, spelled the way it expects them. Named here rather
#: than written as literals below because `auth/authenticator.py` gives them their meaning and this
#: module has to hand it exactly those characters.
CLEAR_TONE = "*"
POUND_TONE = "#"

#: Spelled tone tokens mapped to the single characters the keypad speaks. Lookup is casefolded.
#:
#: **Why this table exists** (`docs/phase4/research-carried-findings.md` §2b, researched 2026-09-10
#: against primary sources). The bidirectional media-streaming frame has **no schema anywhere in
#: Azure's specifications** -- the Call Automation REST spec at `2026-03-12` does not define the
#: websocket frames at all -- and both the .NET and JavaScript SDK parsers hand `data` through
#: untouched. Every primary example on this path shows a bare digit (`"3"` in Microsoft's own
#: sample, `"5"` in the .NET round-trip test). But the only tone vocabulary Azure actually
#: *enumerates* spells tones as words, and it belongs to the `ContinuousDtmfRecognition` webhook
#: path, which is a disjoint mechanism reached by a different switch.
#:
#: **So `*` and `#` have no documented spelling on this path at all**, and the two candidate
#: vocabularies disagree on precisely the two keys that mean something here. On the spelled
#: vocabulary a caller who mis-keyed could never clear, and nothing would say so: the authenticator
#: would ignore `"asterisk"` exactly as it ignores any key it does not recognise.
#:
#: Accepting both is not a guess about which one arrives -- it is what makes the question stop
#: mattering. The vocabularies cannot collide, because every spelled token is at least two
#: characters and every literal tone is one; `TheTwoVocabulariesDoNotCollide` in `tests/test_acs.py`
#: holds that property. **This does not close the question**: Phase 5's first real call must press
#: `*` and `#`, because a digits-only call would leave it exactly as open while looking settled.
TONE_SPELLINGS = {
    "zero": "0", "one": "1", "two": "2", "three": "3", "four": "4",
    "five": "5", "six": "6", "seven": "7", "eight": "8", "nine": "9",
    "asterisk": CLEAR_TONE, "star": CLEAR_TONE,
    "pound": POUND_TONE, "hash": POUND_TONE,
}


def normalise_tone(tone):
    """One DTMF tone in whichever vocabulary it arrived in, as the character the keypad expects.

    Anything unrecognised is returned **unchanged rather than dropped or guessed at**. That is the
    fail-closed direction here: the authenticator ignores a key it does not recognise, so an
    unknown value cannot advance an entry, and passing it through leaves a real call's evidence
    intact for whoever reads it next. `A` through `D` take this path deliberately -- both
    vocabularies carry them and the keypad ignores them either way, so mapping them would be
    ceremony.

    Total, and never raises. No schema constrains this frame, so `None` and a non-string are both
    things that can arrive, and neither may end the call from the inbound relay task.
    """
    if not isinstance(tone, str):
        return tone
    return TONE_SPELLINGS.get(tone.casefold(), tone)


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

    **The DTMF payload is normalised through `TONE_SPELLINGS`** so the keypad sees one vocabulary
    whichever one ACS uses. See that table for why this path has two candidate vocabularies and no
    schema to choose between them.
    """
    msg = json.loads(raw_text)
    kind = msg.get("kind")
    if kind == "DtmfData":
        # Defensively dug out rather than indexed. A malformed DTMF frame must not raise on the
        # inbound relay task, which would end the call: the authenticator ignores a key it does
        # not recognise, and None is one of those.
        return DTMF, normalise_tone((msg.get("dtmfData") or {}).get("data"))
    if kind == "AudioData":
        return AUDIO, msg["audioData"]["data"]
    return OTHER, None


def outbound_audio_frame(b64_audio):
    """Builds one outbound ACS audio frame -- capitalized keys, per the asymmetry above."""
    return json.dumps({"Kind": "AudioData", "AudioData": {"Data": b64_audio}})

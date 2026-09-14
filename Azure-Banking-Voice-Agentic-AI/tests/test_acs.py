"""The ACS media-frame classifier, and the DTMF tone vocabulary it normalises.

Until now `classify_inbound` had no tests of its own and was exercised only through whole calls,
which fed it the one vocabulary the fake transport writes. That is the shape of test that cannot
find the defect this module is about.

**Why the vocabulary is a question at all** (`docs/phase4/research-carried-findings.md` §2b). The
media-streaming websocket frame has **no schema in any Azure specification** -- a scan of the Call
Automation REST spec at `2026-03-12` for `dtmfData` returns nothing, and the contract lives only in
documentation samples and SDK parsers, all of which pass the value through untouched. Every primary
example on this path shows a bare digit. The only *enumerated* tone vocabulary Azure publishes
spells tones as words (`"pound"`, `"asterisk"`, `"one"`), and it belongs to the
`ContinuousDtmfRecognition` webhook path, which is a disjoint mechanism with a separate switch.

So `*` and `#` have **no documented spelling on this path whatsoever**, and the two candidate
vocabularies disagree on exactly the two characters the keypad gives meaning to: star clears, pound
is ignored. On the spelled vocabulary the classifier would hand the authenticator `"asterisk"`, the
authenticator would ignore it, and a caller who mis-keyed a digit could never clear -- silently,
with nothing in any log to say why.

**This is settled by accepting both vocabularies rather than by picking one.** A mapping table costs
nothing, cannot be wrong in a way that matters (the two vocabularies do not collide -- every spelled
token is at least two characters, every literal tone is one), and removes the spelling from the list
of things Phase 5's first real call can fail on. It does not make the answer known: Phase 5 must
still press `*` and `#` on a real call, and a digits-only test call would leave this exactly as open
while looking like it closed.
"""
import asyncio
import json
import unittest

from azbank_voice_agent.auth import authenticator, outcomes
from azbank_voice_agent.core_banking.fake import FakeCoreBankingClient
from azbank_voice_agent.transport import acs


def dtmf(tone):
    """One inbound DTMF frame carrying `tone`, spelled the way ACS spells inbound frames."""
    return json.dumps({"kind": "DtmfData", "dtmfData": {"data": tone}})


class TheLiteralVocabulary(unittest.TestCase):
    """What every primary example on this path actually shows: a bare character."""

    def test_a_literal_digit_arrives_as_itself(self):
        for digit in "0123456789":
            with self.subTest(tone=digit):
                self.assertEqual(acs.classify_inbound(dtmf(digit)), (acs.DTMF, digit))

    def test_the_two_control_keys_arrive_as_themselves(self):
        # The keypad gives both of these meaning, so both have to survive the classifier intact.
        self.assertEqual(acs.classify_inbound(dtmf("*")), (acs.DTMF, "*"))
        self.assertEqual(acs.classify_inbound(dtmf("#")), (acs.DTMF, "#"))


class TheSpelledVocabulary(unittest.TestCase):
    """Azure's own published tone enum, which may or may not be what this path uses."""

    def test_a_spelled_digit_becomes_the_digit(self):
        spelled = [
            "zero", "one", "two", "three", "four",
            "five", "six", "seven", "eight", "nine",
        ]
        for expected, word in enumerate(spelled):
            with self.subTest(tone=word):
                self.assertEqual(
                    acs.classify_inbound(dtmf(word)), (acs.DTMF, str(expected))
                )

    def test_every_spelling_of_clear_becomes_the_clear_key(self):
        # `asterisk` is Azure's enum spelling; `star` is what the same key is called everywhere
        # else and costs one row to accept.
        for word in ("asterisk", "star"):
            with self.subTest(tone=word):
                self.assertEqual(acs.classify_inbound(dtmf(word)), (acs.DTMF, acs.CLEAR_TONE))

    def test_every_spelling_of_pound_becomes_the_pound_key(self):
        for word in ("pound", "hash"):
            with self.subTest(tone=word):
                self.assertEqual(acs.classify_inbound(dtmf(word)), (acs.DTMF, acs.POUND_TONE))

    def test_the_spelling_is_matched_without_regard_to_case(self):
        # Nothing documents the casing either, and the cost of being wrong about it is the same
        # silent failure as being wrong about the word.
        self.assertEqual(acs.classify_inbound(dtmf("Pound")), (acs.DTMF, acs.POUND_TONE))
        self.assertEqual(acs.classify_inbound(dtmf("ASTERISK")), (acs.DTMF, acs.CLEAR_TONE))


class TheTwoVocabulariesDoNotCollide(unittest.TestCase):
    """The property that makes accepting both safe rather than merely convenient."""

    def test_no_literal_tone_is_also_a_spelled_token(self):
        # A one-character tone can never be mistaken for a word, so normalising cannot turn a
        # real tone into a different real tone. If this ever fails, accepting both vocabularies
        # has stopped being free and the table has to become a decision instead.
        for literal in "0123456789*#":
            with self.subTest(tone=literal):
                self.assertNotIn(literal.casefold(), acs.TONE_SPELLINGS)


class TheNormalisedTonesAreTheOnesTheKeypadActsOn(unittest.TestCase):
    """The two constants exist in two modules, and the mapping is worthless if they disagree.

    `transport/acs.py` cannot import `auth/` -- that would point the transport layer at the thing
    it feeds -- so the characters are written down twice and asserted equal here instead. Without
    this, changing the keypad's clear key would leave the classifier still normalising `"asterisk"`
    to the old one, and every spelled clear would be silently ignored.
    """

    def test_the_classifiers_control_tones_are_the_keypads_control_keys(self):
        self.assertEqual(acs.CLEAR_TONE, authenticator.CLEAR)
        self.assertEqual(acs.POUND_TONE, authenticator.POUND)

    def test_a_spelled_clear_really_clears_a_partial_entry(self):
        """End to end through both modules, because that is the failure this is all about.

        Two digits keyed, then `"asterisk"` rather than `"*"`. If the classifier stopped
        normalising, this reports ACCUMULATING or IGNORED instead and the caller's mis-key is
        stuck in the buffer for the rest of the call.
        """
        machine = authenticator.Authenticator(FakeCoreBankingClient())

        async def key_them():
            for tone in ("1", "2"):
                await machine.key(acs.classify_inbound(dtmf(tone))[1])
            return await machine.key(acs.classify_inbound(dtmf("asterisk"))[1])

        self.assertEqual(asyncio.run(key_them()), outcomes.CLEARED)


class AnythingElse(unittest.TestCase):
    """**The DTMF branch** must not raise on the inbound relay task, whatever arrives.

    Stated for that branch rather than for the classifier, because the classifier as a whole is not
    total and this docstring used to say it was (/code-review, 2026-09-10). The audio branch still
    indexes `msg["audioData"]["data"]` directly, so a malformed audio frame raises -- pinned below
    rather than left as folklore. That asymmetry is deliberate on the DTMF side and merely
    inherited on the audio side; whether the audio branch should be made total too is
    `PROJECT_STATE.md` open item 17 rather than a change here, since it is relay behaviour nobody
    asked to alter. That item did not exist when this docstring first claimed it did
    (/code-review, 2026-09-10).
    """

    def test_an_unrecognised_tone_is_passed_through_untouched(self):
        # Not mapped, not guessed at, not dropped. The authenticator ignores a key it does not
        # recognise, so an unknown value fails closed on its own -- and passing it through
        # unchanged is what leaves a real call's evidence intact for whoever reads it next.
        # `A` through `D` land here: both vocabularies carry them and the keypad ignores both.
        #
        # The base64-looking value is deliberately base64 of something that is not a credential.
        # It used to encode the demo PIN, which put a credential in the tree where neither
        # `tests/keyed_values.py` nor its static guard could see it (/code-review, 2026-09-10).
        for tone in ("A", "b", "star-ish", "", "YWJjZA=="):
            with self.subTest(tone=tone):
                self.assertEqual(acs.classify_inbound(dtmf(tone)), (acs.DTMF, tone))

    def test_a_malformed_audio_frame_still_raises(self):
        """The classifier's one non-total branch, pinned as behaviour rather than described.

        Not an endorsement. This is what the code does today, and a test that says so is what makes
        a future decision to change it a deliberate one with a red test to update, rather than a
        silent behaviour change nobody notices.
        """
        with self.assertRaises(KeyError):
            acs.classify_inbound(json.dumps({"kind": "AudioData"}))

    def test_a_missing_or_null_tone_does_not_raise(self):
        self.assertEqual(acs.classify_inbound(dtmf(None)), (acs.DTMF, None))
        self.assertEqual(
            acs.classify_inbound(json.dumps({"kind": "DtmfData"})), (acs.DTMF, None)
        )
        self.assertEqual(
            acs.classify_inbound(json.dumps({"kind": "DtmfData", "dtmfData": None})),
            (acs.DTMF, None),
        )

    def test_a_non_string_tone_does_not_raise(self):
        # No schema constrains this frame, so a number is as possible as anything else.
        self.assertEqual(acs.classify_inbound(dtmf(7)), (acs.DTMF, 7))


class TheOtherFrameKinds(unittest.TestCase):
    """Unchanged by any of the above, and untested until now."""

    def test_an_audio_frame_yields_its_payload(self):
        frame = json.dumps({"kind": "AudioData", "audioData": {"data": "AAAA"}})
        self.assertEqual(acs.classify_inbound(frame), (acs.AUDIO, "AAAA"))

    def test_an_unknown_frame_kind_is_ignored_rather_than_crashed_on(self):
        frame = json.dumps({"kind": "SomethingElse", "data": {}})
        self.assertEqual(acs.classify_inbound(frame), (acs.OTHER, None))

    def test_an_outbound_frame_uses_the_capitalised_spelling(self):
        # The inbound/outbound casing asymmetry is Microsoft's, and is corroborated by their own
        # Python sample on the audio-streaming quickstart page.
        self.assertEqual(
            json.loads(acs.outbound_audio_frame("BBBB")),
            {"Kind": "AudioData", "AudioData": {"Data": "BBBB"}},
        )


if __name__ == "__main__":
    unittest.main()

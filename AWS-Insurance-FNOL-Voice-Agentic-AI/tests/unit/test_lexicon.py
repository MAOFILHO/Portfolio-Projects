"""L1 lexicon tests. Positive cases are drawn verbatim from `docs/phase4/INTENT-TAXONOMY.md`'s canonical
and adversarial injury-phrasing sets (§1's InjuryEscalation examples and §2.4's harder cases) -- these are
not invented fixtures, they're the taxonomy's own test material, exercised here for the first time.
"""
from __future__ import annotations

import pytest

from fnol_voice_agent.agents.lexicon import detect_safety_trigger

# --- Positive cases: INTENT-TAXONOMY.md §1's canonical InjuryEscalation utterances ---

CANONICAL_INJURY_UTTERANCES = [
    "I think I'm hurt.",
    "My passenger isn't moving.",
    "There's blood, I need help.",
    "I want to talk to a real person, someone's hurt.",
]

# --- Positive cases: INTENT-TAXONOMY.md §2.4's harder adversarial phrasings ---

ADVERSARIAL_INJURY_UTTERANCES = [
    "I don't feel right.",
    "My neck's been bothering me since it happened.",
    "He's not saying anything.",
    "I'm fine, but I think the other driver might not be.",
]


@pytest.mark.parametrize("utterance", CANONICAL_INJURY_UTTERANCES)
def test_canonical_injury_utterances_fire(utterance: str) -> None:
    fired, term = detect_safety_trigger(utterance)
    assert fired is True, f"expected a trigger for {utterance!r}"
    assert term


@pytest.mark.parametrize("utterance", ADVERSARIAL_INJURY_UTTERANCES)
def test_adversarial_injury_utterances_fire(utterance: str) -> None:
    fired, term = detect_safety_trigger(utterance)
    assert fired is True, f"expected a trigger for {utterance!r}"
    assert term


# --- Negative cases: ordinary FileAutoClaim slot answers must NOT false-positive ---

BENIGN_CLAIM_UTTERANCES = [
    "My car got hit in the parking lot.",
    "There's a dent in the rear bumper.",
    "The other driver ran a red light and hit my door.",
    "My headlight is broken.",  # deliberately adjacent to "broken" -- no body part nearby
    "I was rear-ended on the highway.",
    "The windshield has a crack in it.",
    "My policy number is PY4821.",
    "It happened yesterday around 5:30 in the afternoon.",
    "No, nobody else was involved.",
    "Yes, I filed a police report.",
]


@pytest.mark.parametrize("utterance", BENIGN_CLAIM_UTTERANCES)
def test_benign_claim_utterances_do_not_fire(utterance: str) -> None:
    fired, term = detect_safety_trigger(utterance)
    assert fired is False, f"false positive on {utterance!r} (matched {term!r})"


def test_no_trigger_on_empty_string() -> None:
    assert detect_safety_trigger("") == (False, None)


def test_matched_term_is_traceable_for_a_known_case() -> None:
    fired, term = detect_safety_trigger("There's blood, I need help.")
    assert fired is True
    assert term == "blood"

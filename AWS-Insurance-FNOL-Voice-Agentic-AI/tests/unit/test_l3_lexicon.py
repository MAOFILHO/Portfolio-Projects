"""L3 lexicon tests -- the hard "agent"/"human" barge-in override (`D74`, `DIALOGUE-POLICIES.md` §8, route
2). Written before `agents/l3_lexicon.py`, per `CLAUDE.md`'s TDD rule.
"""

from __future__ import annotations

import pytest

from fnol_voice_agent.agents.l3_lexicon import detect_agent_override

# --- Positive cases: explicit requests for a human, in several surface forms ---

EXPLICIT_OVERRIDE_UTTERANCES = [
    "I want to talk to a real person.",
    "Can I speak to a human?",
    "Connect me with an agent.",
    "Transfer me to a representative.",
    "Get me an operator.",
    "I need to speak with someone.",
    "Put me through to a person.",
    "I want a human, not a robot.",
    "Can you connect me to customer service?",
]

# --- Positive cases: the bare word alone, the classic IVR override ---

BARE_OVERRIDE_UTTERANCES = [
    "agent",
    "Agent!",
    "operator",
    "human",
    "representative",
    "  person  ",
]

# --- Negative cases: "agent" appears, but not as a request for one ---

NON_OVERRIDE_UTTERANCES = [
    "My agent told me to call this number.",
    "I already spoke to my insurance agent about this.",
    "The claims agent said she'd follow up.",
    "I need to file a claim.",
    "What's the status of my claim?",
    "I was rear-ended this morning.",
    "",
]


@pytest.mark.parametrize("utterance", EXPLICIT_OVERRIDE_UTTERANCES)
def test_explicit_override_phrasings_fire(utterance: str) -> None:
    fired, term = detect_agent_override(utterance)
    assert fired is True, f"expected an override for {utterance!r}"
    assert term


@pytest.mark.parametrize("utterance", BARE_OVERRIDE_UTTERANCES)
def test_bare_override_words_fire(utterance: str) -> None:
    fired, term = detect_agent_override(utterance)
    assert fired is True, f"expected an override for {utterance!r}"
    assert term


@pytest.mark.parametrize("utterance", NON_OVERRIDE_UTTERANCES)
def test_non_override_mentions_do_not_fire(utterance: str) -> None:
    fired, term = detect_agent_override(utterance)
    assert fired is False, f"did not expect an override for {utterance!r}"
    assert term is None


def test_matched_term_is_the_triggering_text_not_the_whole_utterance() -> None:
    _, term = detect_agent_override("Look, I really just want to talk to a real person here.")
    assert term is not None
    assert len(term) < len("Look, I really just want to talk to a real person here.")


def test_case_insensitive() -> None:
    fired, _ = detect_agent_override("I WANT TO SPEAK WITH A HUMAN")
    assert fired is True


def test_injury_and_override_language_in_the_same_utterance_still_fires() -> None:
    """`INTENT-TAXONOMY.md` §1's own canonical InjuryEscalation example carries override language too --
    L3 firing on it is correct; route priority (L1/route 1 over L3/route 2) is the codehook's job, not
    this function's."""
    fired, _ = detect_agent_override("I want to talk to a real person, someone's hurt.")
    assert fired is True

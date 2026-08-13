"""L3's deterministic "agent"/"human" override lexicon (`D74`, `DIALOGUE-POLICIES.md` §8, route 2 --
"caller request"). Pure pattern matching, no model call, same discipline as `agents/lexicon.py`'s L1 --
but this function is called directly by `api/lex_codehook.py`, never wired into the LangGraph pipeline
itself. `D74`'s reasoning: mid-slot-elicitation, an utterance is matched against the active slot type
first, so a caller saying "agent" while a slot is being elicited produces a Lex no-match, not an intent
switch. A seventh Lex intent would be reachable from most states and would *look* reachable from all of
them -- worse than not having one. The codehook can see the raw turn text on every `DialogCodeHook`
invocation regardless of which slot Lex thinks it is filling, which is the property this needs.

**Deliberately simpler than L1.** L1 needs a polarity rule because injury language is asserted-then-
possibly-negated ("nobody was hurt"). A request for a human has no comparable negated form worth
guarding against in this domain -- nobody says "I do NOT want to talk to a person" as a load-bearing
sentence in an FNOL call -- so this module has no negation scope and does not need one. What it does need
is the inverse discipline L1 doesn't: **the trigger words are common enough on their own (`agent`,
`representative`) that a bare substring match would fire on "my agent told me to call" or "the claims
agent said she'd follow up".** Both are real utterances an FNOL caller says routinely and neither is a
request for anything. The fix here is structural rather than a negation rule: `agent`/`representative`/
`person`/`human`/`operator` only fire (a) as the caller's *entire* utterance (the classic bare IVR
override, "Agent!"), or (b) preceded by an explicit request verb (`talk to`, `speak with`, `connect me
to`, `transfer me to`, `get me`, `put me through to`, `I want`, `I need`). "My agent" satisfies neither:
it is not the whole utterance and no request verb precedes it.

**Explicitly not claimed as complete.** This lexicon has not been measured against an independently
generated held-out set the way L1 was (`RESULTS.md` §1) -- that measurement is unscheduled, named here so
it is not mistaken for having been done. What is asserted is narrower and checked by
`tests/unit/test_l3_lexicon.py`: the explicit-request and bare-word forms fire, and the three named false-
positive shapes this project's own domain routinely produces ("my agent", "insurance agent", "claims
agent") do not.
"""

from __future__ import annotations

import re

# The nouns L3 recognises as "a human," in either surface form below.
_HUMAN_NOUNS = r"(?:a |an )?(?:real )?(?:person|human|agent|representative|operator|someone|rep)"

# Form (a): an explicit request verb followed by one of the human nouns, anywhere in the utterance.
# Deliberately does NOT require the noun to be the object of "want"/"need" in a strict grammatical sense
# -- "I want a human, not a robot" and "I want to speak with a human" are both real phrasings and both
# should fire.
_REQUEST_PATTERN = re.compile(
    rf"\b(?:talk|speak)\s+(?:to|with)\s+{_HUMAN_NOUNS}\b"
    rf"|\bconnect(?:ed)?\s+(?:me\s+)?(?:to|with)\s+{_HUMAN_NOUNS}\b"
    rf"|\btransfer(?:red)?\s+(?:me\s+)?to\s+{_HUMAN_NOUNS}\b"
    rf"|\bget\s+me\s+{_HUMAN_NOUNS}\b"
    rf"|\bput\s+me\s+through\s+(?:to\s+)?{_HUMAN_NOUNS}\b"
    rf"|\bi\s+(?:want|need)\s+(?:to\s+(?:talk|speak)\s+(?:to|with)\s+)?{_HUMAN_NOUNS}\b"
    rf"|\bconnect\s+me\s+to\s+customer\s+service\b"
)

# Form (b): the caller's entire utterance is nothing but one of the override nouns (plus punctuation and
# whitespace) -- "Agent!", "operator", "  person  ". Anchored on the whole string, not `search`, which is
# exactly what keeps this from matching "my agent" -- that string is not equal to "agent" once trimmed.
_BARE_WORD_PATTERN = re.compile(
    r"^(?:a |an )?(?:real )?(?:person|human|agent|representative|operator|someone|rep)[!.?]*$"
)


def detect_agent_override(text: str) -> tuple[bool, str | None]:
    """Returns `(fired, matched_term)`, same shape as `agents.lexicon.detect_safety_trigger` so the
    codehook can treat both deterministic checks uniformly."""
    stripped = text.strip()
    if not stripped:
        return False, None

    lowered = stripped.lower()

    bare_match = _BARE_WORD_PATTERN.match(lowered)
    if bare_match:
        return True, bare_match.group(0)

    request_match = _REQUEST_PATTERN.search(lowered)
    if request_match:
        return True, request_match.group(0)

    return False, None

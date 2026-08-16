"""L1's deterministic injury/fatality lexicon (`D12`, `D15`, `ADR-010`). Pure pattern matching, no model
call -- this is what makes L1's position in the graph enforceable (`agents/graph.py`'s dominance check)
rather than merely conventional, and what makes a labelled-set recall failure a debuggable code defect
(`AI-USE-CASE-CARD.md` F1: "a missing lexicon entry") rather than a stochastic one.

Tiers, from strongest to weakest signal:
  1a. Injury-PRESENCE keywords -- assert harm exists, and are therefore the terms a negation can invert.
      Subject to the polarity rule below ("nobody was hurt" is an all-clear, not an injury report).
  1b. Inherently-negative phrases -- "not breathing", "can't feel". The negation IS the emergency, so
      these are structurally exempt from the polarity rule rather than merely ordered before it.
  2.  Third-party status -- a pattern over negation + a responsiveness verb, covering tense and auxiliary
      variants as a class ("isn't moving", "hasn't moved", "won't wake up"). Also exempt from polarity.
  3.  Context-windowed patterns -- weaker words (`bother`, `broken`) firing only when paired with a body
      part inside the SAME CLAUSE, so "broken headlight" does not read as an injury and neither does a
      body part in one clause pairing with a distress word in another.

**Explicitly not claimed as complete, and Phase 6 measured how incomplete.** Against an independently
generated held-out set (`evals/holdout/injury_phrasings_independent.yaml`, authored by an agent that
never read this file), L1 recall was **0.192 before the Phase 6 fix and 0.269 after** -- it misses roughly
three quarters of real indirect injury phrasing, including most euphemisms for death. That is not a
defect to be patched away by adding entries; it is the structural limit of a lexicon, and it is the
reason `SUCCESS-METRICS.md` §2's detector is layered. **L1 carries precision and latency; L2 has to
carry recall.** See `docs/RESULTS.md`.

What the Phase 6 fix did change decisively is the other direction: false-escalation on that same unseen
set fell from **0.412 to 0.059**, because the polarity rule generalises in a way that a keyword list
cannot. `AI-USE-CASE-CARD.md` F1 names novel-phrasing recall as this system's most serious residual
risk; Phase 6 turned that from a stated concern into a measured one.
"""

from __future__ import annotations

import re

# Tier 1a: injury-PRESENCE keywords. These assert that harm exists, which means they are exactly the
# terms a negation can invert -- "nobody was hurt" is an all-clear, not an injury report. Subject to
# `_is_negated` below. Keeping them in their own tuple is what makes the polarity rule a category rather
# than a list of special cases.
_PRESENCE_KEYWORDS: tuple[str, ...] = (
    "hurt",
    "injur",  # injury, injured, injuries
    "bleeding",
    "blood",
    "unresponsive",
    "concussion",
    "dying",
    " dead ",
    "fatal",
    "ambulance",
    "911",
    "paramedic",
    " ems ",
    "chest pain",
    "passed out",
    "knocked out",
    "in pain",
)

# Tier 1b: phrases that already carry their own negation, and whose meaning is the injury.
# "not breathing" must never be suppressed by a negation rule -- the negation IS the emergency.
# Deliberately exempt from `_is_negated`; see its docstring.
_INHERENTLY_NEGATIVE_PHRASES: tuple[str, ...] = (
    "not breathing",
    "isn't breathing",
    "isnt breathing",
    "can't breathe",
    "cant breathe",
    "can't feel",
    "cant feel",
    "not okay",
    "not ok ",
)

# Tier 2: third-party status. Generalised from a literal phrase list to a pattern over
# negation + optional intervening words + a responsiveness verb, so that grammatical variants are
# covered as a class. The previous literal list held "isn't moving" but not "hasn't moved", which is the
# same statement in a different tense and was a real miss (`inj-010`) on the Phase 6 golden set.
#
# Also exempt from `_is_negated`, for the same reason as tier 1b: these phrases are negative by
# construction and the negation is the signal.
_THIRD_PARTY_STATUS_PATTERN = re.compile(
    # `n't` cannot carry a leading \b -- in "isn't" the "n" is preceded by a word character, so \bn't
    # never matches and "isn't moving" would fall straight through. Real regression, caught by the
    # existing Phase 5 canonical-utterance test.
    r"(?:\bnot\b|n't|\bnever\b)\s+(?:\w+\s+){0,3}?"
    r"(?:mov(?:e|es|ed|ing)|respond(?:s|ed|ing)?|answer(?:s|ed|ing)?|"
    r"talk(?:s|ed|ing)?|speak(?:s|ing)?|say(?:s|ing)?\s+anything|wake|woken|conscious)\b"
)

# Tier 3a: body part + distress word, windowed either direction.
#
# The window may NOT cross a clause boundary. Previously `.{0,25}` matched anything, so "I had a knee
# replacement a few years back but it held up fine, no bother" fired -- pairing the "back" of "a few
# years back" with the "bother" of "no bother", across a comma and a "but", in a sentence that says the
# opposite of an injury. Restricting the window to a single clause is the general form of that fix:
# a body part in one clause and a distress word in another are not a statement about each other.
_BODY_PARTS = r"(neck|back|chest|head|leg|arm|shoulder|hip|rib|wrist|ankle|nose|collarbone)"
_DISTRESS_WORDS = r"(hurt(?:s|ing)?|pain(?:ful)?|ache|aching|bother(?:ing)?|broken|fracture[ds]?)"
_WITHIN_CLAUSE = r"(?:(?!\bbut\b|\bthough\b|\balthough\b|\bhowever\b)[^,;.!?]){0,25}"
_BODY_DISTRESS_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(rf"\b{_BODY_PARTS}\b{_WITHIN_CLAUSE}\b{_DISTRESS_WORDS}\b"),
    re.compile(rf"\b{_DISTRESS_WORDS}\b{_WITHIN_CLAUSE}\b{_BODY_PARTS}\b"),
)

# Tier 3b: vague self-distress, no body part named.
_VAGUE_DISTRESS_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bdon'?t feel right\b"),
    re.compile(r"\bfeel(?:s|ing)? (?:off|weird|strange|funny)\b"),
    re.compile(r"\bsomething'?s wrong with (?:me|him|her|them)\b"),
)

# Tier 3c: self-negating contrastive phrasing -- "I'm fine, but the other driver might not be."
# INTENT-TAXONOMY.md §2.4's named adversarial case for L1's lexicon not short-circuiting on the caller's
# own stated status alone.
_CONTRASTIVE_OTHER_PARTY_PATTERN = re.compile(
    r"\bi'?m (?:fine|ok|okay)\b.{0,60}"
    r"\b(?:he|she|they|the other (?:driver|passenger)|my passenger)\b.{0,30}"
    r"\b(?:might not|may not|maybe not|not)\b"
)


# --- Polarity ---------------------------------------------------------------------------------------
#
# The lexicon previously had no notion of polarity at all: it matched injury words as bare substrings,
# so "nobody was hurt" fired on `hurt` and "no injuries at all" fired on `injur`. Phase 6's held-out
# measurement found seven false positives and every one was an instance of this single class, not seven
# separate mistakes -- which is why the fix is a scope rule rather than seven exclusions.

# `n't` is matched WITHOUT a leading \b and without a trailing \b requirement on the contraction as a
# whole. In "don't" the "n" is preceded by "o", so `\bn't\b` matches nothing -- meaning that before this
# was corrected, no -n't contraction registered as a negation at all and only the handful spelled out
# explicitly in the list worked. This is the second instance of the same mistake in this module (the
# third-party status pattern had it too), which is why it is now a named hazard in the comment rather
# than a silently-correct regex: \b does not do what it looks like it does immediately before an
# apostrophe-t contraction.
_NEGATION_CUES = re.compile(
    r"(?:n't|n’t|\b(?:no|not|nobody|no one|noone|none|nothing|never|without|" r"nt|cannot)\b)"
)

# A negation governs a term only within the same clause. "Nobody was hurt, the car is wrecked" negates
# `hurt`; "He's hurt, but nobody called an ambulance" does not negate `hurt`.
_CLAUSE_SPLIT = re.compile(r"[,;.!?]|\bbut\b|\bthough\b|\balthough\b|\bhowever\b")


def _is_negated(text: str, match_start: int) -> bool:
    """True when a negation cue governs the term at `match_start`.

    Scope is the clause containing the term, looking only *backwards* from it. Backwards only is a real
    limitation, deliberately taken: "the ambulance came out but they said there was no need for anyone
    to go in" negates `ambulance` from the right, and this returns False for it. Handling
    right-scoped all-clear assertions would be a second, larger category, and the only evidence for it
    sits in the independent held-out set -- building it would mean fixing against held-out data and
    would spend the one uncontaminated measurement this phase has. It is recorded as an open gap
    instead. See `docs/RESULTS.md`.

    Tier 1b and tier 2 never reach this function: their negation *is* the signal, and running a
    suppression rule over "not breathing" would invert the most important detection in the system.
    """
    clause_start = 0
    for boundary in _CLAUSE_SPLIT.finditer(text[:match_start]):
        clause_start = boundary.end()
    return _NEGATION_CUES.search(text[clause_start:match_start]) is not None


def detect_safety_trigger(text: str) -> tuple[bool, str | None]:
    """Returns `(fired, matched_term)`. `matched_term` is the exact keyword/pattern text that fired,
    logged into `AgentState.l1_matched_term` so a missed-then-fixed case in Phase 6/7 traces back to
    exactly which lexicon entry was added, not just "L1 now catches this.\" """
    lowered = f" {text.lower()} "

    # Inherently-negative phrases and third-party status first, and never negation-scoped.
    for keyword in _INHERENTLY_NEGATIVE_PHRASES:
        if keyword in lowered:
            return True, keyword.strip()

    status_match = _THIRD_PARTY_STATUS_PATTERN.search(lowered)
    if status_match:
        return True, status_match.group(0).strip()

    # Presence keywords, suppressed when a negation governs them in the same clause.
    for keyword in _PRESENCE_KEYWORDS:
        index = lowered.find(keyword)
        while index != -1:
            if not _is_negated(lowered, index):
                return True, keyword.strip()
            index = lowered.find(keyword, index + 1)

    for pattern in _BODY_DISTRESS_PATTERNS + _VAGUE_DISTRESS_PATTERNS:
        match = pattern.search(lowered)
        if match and not _is_negated(lowered, match.start()):
            return True, match.group(0).strip()

    match = _CONTRASTIVE_OTHER_PARTY_PATTERN.search(lowered)
    if match:
        return True, match.group(0).strip()

    return False, None

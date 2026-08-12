"""L1's deterministic injury/fatality lexicon (`D12`, `D15`, `ADR-010`). Pure pattern matching, no model
call -- this is what makes L1's position in the graph enforceable (`agents/graph.py`'s dominance check)
rather than merely conventional, and what makes a labelled-set recall failure a debuggable code defect
(`AI-USE-CASE-CARD.md` F1: "a missing lexicon entry") rather than a stochastic one.

Three tiers, from strongest to weakest signal:
  1. Unambiguous injury/fatality keywords -- a bare substring match is enough (`INTENT-TAXONOMY.md`'s
     canonical set: "I think I'm hurt", "There's blood, I need help").
  2. Third-party status phrases -- catches a caller who negates their *own* injury but not another
     party's (`INTENT-TAXONOMY.md` §2.4: "My passenger isn't moving.", "He's not saying anything.").
  3. Context-windowed patterns -- weaker individual words (`bother`, `broken`) that only fire paired with
     a body-part or explicit-distress word nearby, to avoid "broken headlight" reading as an injury while
     still catching "My neck's been bothering me since it happened."

**Explicitly not claimed as complete.** `AI-USE-CASE-CARD.md` F1 names novel/incomplete-lexicon phrasing
as this system's most serious residual risk, measured (not solved) via a held-out novel-phrasing metric in
Phase 6/7 -- this module's job is to make the *labelled* set enforceable to zero via fix-and-re-run
(`D15`), not to claim unbounded natural-language coverage.
"""
from __future__ import annotations

import re

# Tier 1: unambiguous on their own.
_STRONG_KEYWORDS: tuple[str, ...] = (
    "hurt",
    "injur",  # injury, injured, injuries
    "bleeding",
    "blood",
    "unconscious",
    "unresponsive",
    "not breathing",
    "isn't breathing",
    "isnt breathing",
    "can't breathe",
    "cant breathe",
    "concussion",
    "dying",
    " dead ",
    "fatal",
    "ambulance",
    "911",
    "paramedic",
    " ems ",
    "chest pain",
    "can't feel",
    "cant feel",
    "passed out",
    "knocked out",
    "not okay",
    "not ok ",
    "in pain",
)

# Tier 2: third-party status, catches a caller negating someone else's condition even while describing
# their own as fine.
_THIRD_PARTY_KEYWORDS: tuple[str, ...] = (
    "not moving",
    "isn't moving",
    "isnt moving",
    "not responding",
    "isn't responding",
    "isnt responding",
    "not saying anything",
    "isn't saying anything",
    "isnt saying anything",
    "not talking",
    "isn't talking",
    "isnt talking",
)

# Tier 3a: body part + distress word, windowed either direction.
_BODY_PARTS = r"(neck|back|chest|head|leg|arm|shoulder|hip|rib|wrist|ankle|nose|collarbone)"
_DISTRESS_WORDS = r"(hurt(?:s|ing)?|pain(?:ful)?|ache|aching|bother(?:ing)?|broken|fracture[ds]?)"
_BODY_DISTRESS_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(rf"\b{_BODY_PARTS}\b.{{0,25}}\b{_DISTRESS_WORDS}\b"),
    re.compile(rf"\b{_DISTRESS_WORDS}\b.{{0,25}}\b{_BODY_PARTS}\b"),
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


def detect_safety_trigger(text: str) -> tuple[bool, str | None]:
    """Returns `(fired, matched_term)`. `matched_term` is the exact keyword/pattern text that fired,
    logged into `AgentState.l1_matched_term` so a missed-then-fixed case in Phase 6/7 traces back to
    exactly which lexicon entry was added, not just "L1 now catches this.\""""
    lowered = f" {text.lower()} "

    for keyword in _STRONG_KEYWORDS + _THIRD_PARTY_KEYWORDS:
        if keyword in lowered:
            return True, keyword.strip()

    for pattern in _BODY_DISTRESS_PATTERNS + _VAGUE_DISTRESS_PATTERNS:
        match = pattern.search(lowered)
        if match:
            return True, match.group(0).strip()

    match = _CONTRASTIVE_OTHER_PARTY_PATTERN.search(lowered)
    if match:
        return True, match.group(0).strip()

    return False, None

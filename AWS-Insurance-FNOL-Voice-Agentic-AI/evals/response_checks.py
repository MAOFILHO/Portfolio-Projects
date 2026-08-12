"""Deterministic response-quality detectors — Stage 4, Marco's carry-in 1 (`CF5`).

## What this is for

Phase 5 Stage 8 established, with real evidence, that `RentalTowingEntitlement`'s redundancy defect
survives the Phase 4 prompt fix. Two real trials, same prompt, same claim: one clean answer, one that
restated "8 days remaining" in a third sentence having already given it in the second. The fix is
probabilistic, not deterministic.

Marco's instruction at Phase 6 approval was that this stop being a hypothetical: the check must catch
that specific output, and it must be red today. Both real outputs are committed verbatim in
`fixtures/known_bad/`, and `tests/unit/test_response_checks.py` proves the detector flags the bad ones
and leaves the clean one alone.

## Why deterministic and not judge-scored

The defect is mechanically visible: a quantity asserted in one sentence and asserted again in another.
Handing that to an LLM judge would make a cheap exact check expensive, stochastic, and arguable — and
would put a judge in the loop for a property that has an exact answer. Judges are for groundedness and
relevance, where there is no exact answer. This is not that.

## The two checks are separate on purpose

Stage 8 found *two* divergences in the same output, and they have different fixes:

1. **Redundancy by restatement** — the same fact twice. A prompt/length problem.
2. **General mechanics leaked** — corpus-level cap figures volunteered alongside a caller-specific
   answer, against the prompt's explicit "no general mechanics" instruction. A grounding/scope problem.

Both real Stage 8 trials leaked general mechanics, including the one that was clean on redundancy.
Collapsing them into a single "answer quality" score would hide that the cleaner answer still had one of
the two problems.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures" / "known_bad"

# A quantity is a number plus the thing it counts. Bare numbers are excluded deliberately: "8" alone is
# ambiguous between days, dollars and a claim-number fragment, and pairing on bare integers produces
# false matches on any answer that happens to mention two figures.
_QUANTITY_RE = re.compile(
    r"(?:(?P<currency>\$)\s?(?P<amount>[\d,]+(?:\.\d{2})?)"
    r"|(?P<value>\b\d[\d,]*\b)\s*(?P<unit>days?|dollars?|weeks?|per cent|percent|%))",
    re.IGNORECASE,
)

# The postfix form: unit first, value after a copula — "your remaining rental days is 8".
#
# Added because the Phase 4 known-bad fixture was NOT caught by the prefix pattern alone, which is
# exactly what a second real fixture is for. Both bad outputs restate the same fact; only one of them
# does it in the word order the first regex anticipated. A detector validated against a single example
# would have shipped looking correct.
#
# The gap is bounded to a short span so it cannot bridge unrelated clauses and manufacture a match.
_POSTFIX_QUANTITY_RE = re.compile(
    r"\b(?P<unit>days?|dollars?|weeks?)\b[^.;!?]{0,24}?\b(?:is|are|:|totals?|equals?)\s+"
    r"(?P<value>\d[\d,]*)\b",
    re.IGNORECASE,
)

_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")

# Corpus-level rental mechanics from endorsements.md. Present in a caller-specific answer, these are the
# "general mechanics" the RentalTowingEntitlement prompt explicitly instructs the model not to restate.
_GENERAL_MECHANICS_PATTERNS = (
    re.compile(r"\b(?:up to|maximum of|max(?:imum)?)\s+20\s+days?\b", re.IGNORECASE),
    re.compile(r"\b20\s+days?\s+(?:per claim|maximum|max)\b", re.IGNORECASE),
    re.compile(r"\$\s?50\s*(?:/|\s*per\s*)day", re.IGNORECASE),
    re.compile(r"\$\s?1,?000\s*(?:total|cap|per claim)", re.IGNORECASE),
)


@dataclass(frozen=True)
class RedundancyFinding:
    quantity: str
    sentence_indices: tuple[int, ...]
    sentences: tuple[str, ...]


@dataclass(frozen=True)
class ResponseCheckResult:
    text: str
    sentence_count: int
    word_count: int
    redundancies: list[RedundancyFinding] = field(default_factory=list)
    leaked_general_mechanics: list[str] = field(default_factory=list)

    @property
    def is_redundant(self) -> bool:
        return bool(self.redundancies)

    @property
    def leaks_general_mechanics(self) -> bool:
        return bool(self.leaked_general_mechanics)


def split_sentences(text: str) -> list[str]:
    return [s for s in _SENTENCE_SPLIT_RE.split(text.strip()) if s]


def extract_quantities(sentence: str) -> set[str]:
    """Normalised quantities in one sentence, e.g. {"8 day", "$400"}.

    Units are singularised so "8 days" and "8 day" collide, which is the point — a restatement rarely
    reuses the exact wording, and a detector that required it would miss most real cases.
    """
    found: set[str] = set()
    for match in _QUANTITY_RE.finditer(sentence):
        if match.group("currency"):
            found.add(f"${match.group('amount').replace(',', '')}")
        else:
            unit = match.group("unit").lower().rstrip("s")
            found.add(f"{match.group('value').replace(',', '')} {unit}")
    for match in _POSTFIX_QUANTITY_RE.finditer(sentence):
        unit = match.group("unit").lower().rstrip("s")
        found.add(f"{match.group('value').replace(',', '')} {unit}")
    return found


def find_redundancies(text: str) -> list[RedundancyFinding]:
    """A quantity asserted in more than one sentence.

    Within a single sentence is fine — "you have used 12 of your 20 days, so 8 remain" is one coherent
    statement, not a restatement. Across sentences is the defect: the caller has already been told, and
    on a voice call every extra sentence is dead time against the 1,800 ms turn budget.
    """
    sentences = split_sentences(text)
    positions: dict[str, list[int]] = {}
    for index, sentence in enumerate(sentences):
        for quantity in extract_quantities(sentence):
            positions.setdefault(quantity, []).append(index)

    return [
        RedundancyFinding(
            quantity=quantity,
            sentence_indices=tuple(indices),
            sentences=tuple(sentences[i] for i in indices),
        )
        for quantity, indices in sorted(positions.items())
        if len(indices) > 1
    ]


def find_leaked_general_mechanics(text: str) -> list[str]:
    """Corpus-level cap figures volunteered in a caller-specific entitlement answer."""
    return [m.group(0) for pattern in _GENERAL_MECHANICS_PATTERNS if (m := pattern.search(text))]


def check_response(text: str) -> ResponseCheckResult:
    return ResponseCheckResult(
        text=text,
        sentence_count=len(split_sentences(text)),
        word_count=len(text.split()),
        redundancies=find_redundancies(text),
        leaked_general_mechanics=find_leaked_general_mechanics(text),
    )


def load_fixture(name: str) -> str:
    return (FIXTURES_DIR / name).read_text().strip()

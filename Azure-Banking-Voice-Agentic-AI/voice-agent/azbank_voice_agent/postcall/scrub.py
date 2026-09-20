"""A deterministic number scrub, run on whatever the PII service hands back (Phase 8, ADR-007).

Azure AI Language does not promise to catch a bare digit string -- its own transparency note says
"without context, a ten-digit number is just a number" (docs/phase8/research-postcall-adapters.md,
Q1f). So the redactor treats the service as one layer and masks anything number-shaped itself:
digit runs of four or more (allowing a space or hyphen between digits, as in a card or phone
number), and four or more spoken digits in a row, because a voice transcript spells numbers out.

Deliberately blunt. It will mask a year or a large round amount too; over-masking a call
transcript costs nothing, and a leaked account number cannot be taken back.
"""
import re

MASK = "[REDACTED]"

_DIGIT_RUN = re.compile(r"\d(?:[ -]?\d){3,}")

_DIGIT_WORD = r"(?:zero|oh|one|two|three|four|five|six|seven|eight|nine)"
_SPOKEN_RUN = re.compile(rf"\b{_DIGIT_WORD}(?:[ ,-]+{_DIGIT_WORD}){{3,}}\b", re.IGNORECASE)


def scrub_numbers(text):
    return _SPOKEN_RUN.sub(MASK, _DIGIT_RUN.sub(MASK, text))

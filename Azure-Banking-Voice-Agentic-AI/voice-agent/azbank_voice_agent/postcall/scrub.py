"""A deterministic number scrub, run on whatever the PII service hands back (Phase 8, ADR-007).

Azure AI Language does not promise to catch a bare digit string -- its own transparency note says
"without context, a ten-digit number is just a number" (docs/phase8/research-postcall-adapters.md,
Q1f). So the redactor treats the service as one layer and masks anything number-shaped itself:
a chain of ten or more digits joined by up to eight characters of punctuation or whitespace (a phone
number in whatever shape, and anything longer), a run of four or more digits joined by one or two
whitespace characters (a newline and a non-breaking space count), hyphens, dashes, slashes, underscores or
middle dots, and four or more spoken digits in a row, because a voice transcript spells numbers out.

The chain is masked whole, from its first digit to its last: an earlier pattern that took ten digits
out of a longer run left the tail behind, and one that knew only a few separators left the first two
groups of `416/555/0199`; a gap capped at three characters left the area code of `416 .. 555 .. 0199`,
which the first pattern had masked (the Phase 8 gate reviews). The chain cannot be the only rule, because it
allows a dot or a closing parenthesis between digits, which the short runs cannot without eating
`$12.50` and `4.25 percent`; the dollar sign is never a separator, so a list of amounts stays apart.
A dotted seven-digit local number (`555.0199`) is its own pattern for the same reason.

Deliberately blunt. It will mask a year or a large round amount too; over-masking a call
transcript costs nothing, and a leaked account number cannot be taken back.
"""
import re

MASK = "[REDACTED]"

# Up to eight characters that are neither a letter, a digit nor a dollar sign, between two digits.
# `\w` covers letters, digits and the underscore, so the underscore is allowed back in by hand.
_LINK = r"(?:[^\w$]|_){0,8}"
_LONG_CHAIN = re.compile(rf"[+(]?\d(?:{_LINK}\d){{9,}}")
_DOTTED_LOCAL = re.compile(r"\b\d{3}\.\d{4}\b")
_DIGIT_RUN = re.compile(r"\d(?:[\s\-\u2010-\u2015/_\u00b7]{0,2}\d){3,}")

_DIGIT_WORD = r"(?:zero|oh|one|two|three|four|five|six|seven|eight|nine)"
_SPOKEN_RUN = re.compile(rf"\b{_DIGIT_WORD}(?:[ ,-]+{_DIGIT_WORD}){{3,}}\b", re.IGNORECASE)


def scrub_numbers(text):
    text = _LONG_CHAIN.sub(MASK, text)
    text = _DOTTED_LOCAL.sub(MASK, text)
    text = _DIGIT_RUN.sub(MASK, text)
    return _SPOKEN_RUN.sub(MASK, text)

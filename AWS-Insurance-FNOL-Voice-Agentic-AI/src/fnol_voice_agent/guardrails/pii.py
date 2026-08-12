"""`ADR-011` Layer 1 redaction -- transcript/log PII scrubbing, per the boundary table below.

**THE BOUNDARY (`ADR-011`, formalizing D16) -- read this before calling anything in this module:**

| Store                                             | Redact? |
|----------------------------------------------------|---------|
| Structured claim record (DynamoDB)                  | **No.** Never pass structured-record fields through this module. `loss_datetime`, `loss_location`, VIN, plate, policy #, claim #, and standard PII are the record's payload -- the whole reason the record exists -- and stay unredacted there by design. |
| Persisted transcript                                | **Yes, always**, before any line is durably written. |
| Application logs / traces / metrics                 | **Yes, always.** No handler in this project logs a raw event object wholesale (`docs/phase2/THREAT-MODEL.md`'s PII-leakage section, naming repo 6's `console.log(JSON.stringify(event))` as the failure mode this rules out). |
| Eval / red-team fixtures                            | Synthetic only -- not this module's concern (nothing real ever enters those fixtures to redact). |

Getting this backwards in either direction is a defect, not a style choice: redacting the structured record
destroys the claim's own data (the fields the business record exists to hold); *failing* to redact a
transcript or log line violates `CLAUDE.md`'s "PII redaction on every transcript before it is persisted or
logged" and defeats `ADR-011`'s "never written anywhere, not even transiently" claim. **Stage 6/7: call
`redact_for_transcript` only on transcript lines and log strings, never on a `models/` claim/FNOL object or
its serialized form.**

**Placeholder format:** every redacted span is replaced with `[REDACTED:<TYPE>]`, where `<TYPE>` is one of
`POLICY_NUMBER`, `CLAIM_NUMBER`, `VIN`, `PLATE`, `DRIVERS_LICENCE`, `POLICE_REPORT_NUMBER`, `PHONE`, `EMAIL`,
`ADDRESS`, `DATE_TIME`, `LOCATION`. Chosen over a blank/asterisk-mask because it's self-describing in a log
line a human is reading later, and because a downstream consumer can `re.search(r"\\[REDACTED:\\w+\\]", ...)`
to confirm redaction happened without needing to know this module's exact category list in advance.

---

**WHAT THIS MODULE CATCHES, AND WHAT IT DOESN'T -- read honestly, not aspirationally, per this project's "no
invented metrics or capabilities" discipline (`CLAUDE.md`):**

- **The six structured identifier formats** (policy #, claim #, VIN, plate, driver's licence, police report
  #) are matched by deterministic, format-anchored regex derived from `validation/identifiers.py`'s own
  constants (`POLICY_NUMBER_RE`, `CLAIM_NUMBER_RE`, `PLATE_RE`, `DRIVERS_LICENCE_RE`, `POLICE_REPORT_RE` --
  reused, not retyped; see `_unanchored` below) plus a VIN shape check defined here (`identifiers.py` has no
  standalone VIN format constant, only check-digit *functions*). Reliable for anything that actually matches
  this project's own generated formats. `ADR-011` names the residual gap explicitly: "a policy number read
  with extra pauses or a homophone substitution... may not be caught by Layer 1's deterministic pass" --
  that's a real, accepted limitation, not something this module claims to solve.
- **Phone (this project's synthetic `555-####` exchange convention), email, and street-address-shaped
  strings** are matched by deterministic regex, as a defense-in-depth complement to Bedrock Guardrails' own
  PII entity filters (`ADR-011` assigns the general "name, phone, email, address, and similar" taxonomy to
  Guardrails, Layer 1's other half) -- **not a substitute for them.** These patterns are reasonably general
  (the phone pattern also matches an optional 3-digit area-code prefix; the address pattern matches common
  English street suffixes and the French `Rue <name>` construction used in this project's own synthetic
  data) but not exhaustive -- a non-555 phone number, a PO box, or an unusual email TLD may not match.
- **`DATE_TIME` and `LOCATION` are redacted from free text**, reversing the Phase 0 guidance that treated
  `DATE_TIME` as exempt (`ADR-011`'s named reversal of `docs/phase0/DOMAIN-ARTIFACTS.md`) -- because date +
  time + location together are a quasi-identifier. **This is the hardest category this module attempts, and
  `ADR-011` says so plainly:** "free-text location redaction is genuinely hard... a modeling problem no
  second pass eliminates." The regex heuristics here (ISO dates, common month-name dates, clock times,
  relative-day words; street intersections, highway/route references) will catch a meaningful slice of
  plainly-phrased mentions and **will miss creatively-phrased ones** -- `ADR-011`'s own example, "right
  outside my kids' school on Maple," has no numeric or keyword anchor a regex can reliably find. This is
  exactly the residual risk `ADR-011` assigns to Layer 2 (an async, post-call, cross-turn re-scan over the
  already-redacted transcript) -- this module is Layer 1 only, a single per-turn pass, and does not claim to
  close that gap by itself.
- **Personal names are NOT detected by this module at all -- by design, not by oversight.** A regex cannot
  reliably distinguish "Devon Whitfield" (a name) from "Devon Street" (part of an address) or "Devon" (a
  place) with any real confidence, and shipping a name detector that silently misses most real names while
  implying coverage would be worse than shipping none. Per `ADR-011`'s own Layer 1 design, general name
  detection is Bedrock Guardrails' PII entity filter's job ("the standard entity taxonomy -- name, phone,
  email, address, and similar"), not this deterministic module's. **A caller's name is not redacted from a
  transcript by this function alone** -- callers relying on this module in isolation (e.g. any test or tool
  that doesn't also run Guardrails) should not assume names are scrubbed.
"""

from __future__ import annotations

import re

from fnol_voice_agent.validation.identifiers import (
    CLAIM_NUMBER_RE,
    DRIVERS_LICENCE_RE,
    PLATE_RE,
    POLICE_REPORT_RE,
    POLICY_NUMBER_RE,
)

# --- Reused identifier patterns, adapted for substring search --------------------------------------------


def _unanchored(compiled: re.Pattern[str]) -> re.Pattern[str]:
    """Derives a substring-search regex from one of `validation/identifiers.py`'s full-match (`^...$`)
    constants, reusing its exact pattern body rather than retyping the format a second time (the instruction
    this module was built under: "REUSE these patterns... don't redefine them a second time"). Wrapping in
    `\\b...\\b` keeps the derived pattern requiring the *whole* token -- it won't fire on a partial match
    buried inside a longer digit/letter run, since every one of these patterns starts and ends on a word
    character.
    """
    body = compiled.pattern
    if not (body.startswith("^") and body.endswith("$")):
        raise ValueError(f"expected a fully-anchored ^...$ pattern, got {body!r}")
    return re.compile(rf"\b{body[1:-1]}\b")


POLICY_NUMBER_EMBEDDED_RE = _unanchored(POLICY_NUMBER_RE)
CLAIM_NUMBER_EMBEDDED_RE = _unanchored(CLAIM_NUMBER_RE)
PLATE_EMBEDDED_RE = _unanchored(PLATE_RE)
DRIVERS_LICENCE_EMBEDDED_RE = _unanchored(DRIVERS_LICENCE_RE)
POLICE_REPORT_EMBEDDED_RE = _unanchored(POLICE_REPORT_RE)

# VIN has no standalone format constant in identifiers.py (only check-digit functions operating on an
# assumed-17-char VIN) -- defined here, per DATA-CONTRACTS.md §3: 17 characters from the standard VIN
# alphabet, which excludes I/O/Q (they're reserved to avoid confusion with 1/0/0 -- this project's synthetic
# VINs, like all real ones, never contain them).
VIN_SHAPE_RE = re.compile(r"\b[A-HJ-NPR-Z0-9]{17}\b")

# --- Standard PII: phone / email / address ----------------------------------------------------------------

# This project's synthetic data uses the reserved 555 exchange for every phone number (docs/phase0
# convention, e.g. "555-0142"). Matches a bare "555-####" and, more generally, an optional 3-digit prefix
# (an area code with no parentheses) ahead of it -- "416-555-0142" -- with "-", ".", or a space as separator.
PHONE_RE = re.compile(r"\b(?:\d{3}[-.\s])?555[-.\s]?\d{4}\b")

EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w-]+\.[A-Za-z]{2,}\b")

_STREET_SUFFIXES = (
    r"Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Crescent|Cres|Drive|Dr|Lane|Ln|Court|Ct|"
    r"Place|Pl|Way|Circle|Cir|Trail|Terrace|Row|Close|Gate|Grove"
)
_CA_PROVINCES = r"ON|QC|BC|AB|MB|SK|NS|NB|NL|PE|YT|NT|NU"

# Matches "<number> <name> <suffix>" (English, e.g. "48 Birchwood Crescent") or "<number> Rue <name>"
# (French, e.g. "12 Rue des Erables" -- this project's own synthetic data convention), each with an optional
# trailing ", <City>, <Province>" so a full "48 Birchwood Crescent, Mississauga, ON" is redacted as one span
# rather than leaving the city/province fragment behind.
ADDRESS_RE = re.compile(
    rf"\b\d{{1,6}}\s+(?:"
    rf"Rue\s+[A-Za-z][A-Za-z'\-]*(?:\s+[A-Za-z][A-Za-z'\-]*){{0,4}}"
    rf"|[A-Za-z][A-Za-z'\-]*(?:\s+[A-Za-z][A-Za-z'\-]*){{0,3}}\s+(?:{_STREET_SUFFIXES})"
    rf")\b"
    rf"(?:,?\s+[A-Za-z][A-Za-z'\-]*(?:\s+[A-Za-z][A-Za-z'\-]*)?,\s*(?:{_CA_PROVINCES})\b)?",
    re.IGNORECASE,
)

# --- DATE_TIME / LOCATION quasi-identifiers (D16 / ADR-011) -----------------------------------------------

_MONTHS = (
    r"January|February|March|April|May|June|July|August|September|October|November|December|"
    r"Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sept|Sep|Oct|Nov|Dec"
)
_RELATIVE_DAY_PHRASES = (
    r"yesterday|today|tonight|last night|this morning|this afternoon|this evening|"
    r"this week|last week|last month"
)

DATE_TIME_RE = re.compile(
    rf"\b(?:"
    rf"\d{{4}}-\d{{2}}-\d{{2}}"  # ISO date: 2026-08-11
    rf"|(?:{_MONTHS})\s+\d{{1,2}}(?:st|nd|rd|th)?(?:,?\s*\d{{4}})?"  # "August 11[, 2026]"
    rf"|\d{{1,2}}(?:st|nd|rd|th)?\s+(?:{_MONTHS})(?:,?\s*\d{{4}})?"  # "11th August[, 2026]"
    rf"|\d{{1,2}}:\d{{2}}(?:\s?(?:am|pm))?"  # "5:30[pm]" -- optional whitespace only consumed
    rf"|\d{{1,2}}\s?(?:am|pm)"  # "5pm"                     together with a trailing am/pm, never bare
    rf"|{_RELATIVE_DAY_PHRASES}"
    rf")\b",
    re.IGNORECASE,
)

_HIGHWAY_RE_PART = r"(?:Highway|Hwy|Route|Rte)\.?\s*\d{1,4}"
_INTERSECTION_RE_PART = (
    r"(?:corner of|intersection of)\s+[A-Z][\w'\-]*(?:\s+[A-Z][\w'\-]*){0,3}"
    r"\s+and\s+[A-Z][\w'\-]*(?:\s+[A-Z][\w'\-]*){0,3}"
)
_STREET_AND_STREET_RE_PART = (
    rf"[A-Z][a-z]+\s+(?:{_STREET_SUFFIXES})\s+and\s+[A-Z][a-z]+\s+(?:{_STREET_SUFFIXES})"
)

# Deliberately narrow -- see module docstring's honesty note. Catches named-street intersections and
# highway/route references; does not attempt landmark-relative phrasing ("near the school on Maple"), which
# ADR-011 itself says no single-pass regex can reliably catch.
LOCATION_RE = re.compile(
    rf"\b(?:{_INTERSECTION_RE_PART}|{_STREET_AND_STREET_RE_PART}|{_HIGHWAY_RE_PART})\b",
    re.IGNORECASE,
)

# --- The combined boundary function -------------------------------------------------------------------

# Order matters: most-specific/format-anchored patterns first (so a structured identifier is never partially
# consumed by a broader heuristic pattern applied first), heuristic DATE_TIME/LOCATION passes last. Once a
# span is replaced with a "[REDACTED:<TYPE>]" placeholder, later passes in this list operate on that
# placeholder text, which by construction doesn't match any earlier or later category's pattern.
_REDACTION_PASSES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("POLICY_NUMBER", POLICY_NUMBER_EMBEDDED_RE),
    ("CLAIM_NUMBER", CLAIM_NUMBER_EMBEDDED_RE),
    ("VIN", VIN_SHAPE_RE),
    ("PLATE", PLATE_EMBEDDED_RE),
    ("DRIVERS_LICENCE", DRIVERS_LICENCE_EMBEDDED_RE),
    ("POLICE_REPORT_NUMBER", POLICE_REPORT_EMBEDDED_RE),
    ("PHONE", PHONE_RE),
    ("EMAIL", EMAIL_RE),
    ("ADDRESS", ADDRESS_RE),
    ("DATE_TIME", DATE_TIME_RE),
    ("LOCATION", LOCATION_RE),
)


def redact_for_transcript(text: str) -> str:
    """Applies every detector in `_REDACTION_PASSES`, in order, replacing each matched span with
    `[REDACTED:<TYPE>]`. This is the one function Stage 6/7 should call before a transcript line or log
    string is durably written -- see the module docstring's boundary table for exactly which stores that
    means (never the structured claim record).

    Text with none of the above categories present passes through byte-for-byte unchanged.
    """
    redacted = text
    for label, pattern in _REDACTION_PASSES:
        redacted = pattern.sub(f"[REDACTED:{label}]", redacted)
    return redacted


__all__ = [
    "POLICY_NUMBER_EMBEDDED_RE",
    "CLAIM_NUMBER_EMBEDDED_RE",
    "VIN_SHAPE_RE",
    "PLATE_EMBEDDED_RE",
    "DRIVERS_LICENCE_EMBEDDED_RE",
    "POLICE_REPORT_EMBEDDED_RE",
    "PHONE_RE",
    "EMAIL_RE",
    "ADDRESS_RE",
    "DATE_TIME_RE",
    "LOCATION_RE",
    "redact_for_transcript",
]

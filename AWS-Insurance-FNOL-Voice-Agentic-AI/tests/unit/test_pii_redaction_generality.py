"""`D124`/`D125`/`OI46`/`OI47` -- the generality check `guardrails/pii.py`'s test suite never had until this
file existed.

**The gap this closes, precisely.** `OI47` (2026-08-17, report-only) found that `test_pii_redaction.py`'s
methodology could not distinguish a general pattern from a narrow one that happened to match its own
fixture: every test in that file asks "does this catch my synthetic fixture," never "does this catch
something shaped differently from my synthetic fixture." `EMAIL_RE`'s generality turned out to be real
(design in the regex), but the test suite provided no evidence of that beyond one lucky coincidence
(`priya.nakamura@example.com` happens to share real-world email shape). `PHONE_RE`'s narrowness
(`D124`/`OI46`, fixed in the same session as this file) would have passed an identically-shaped test just
as cleanly. This file makes that distinction checkable, not just arguable.

**What this deliberately is NOT.** The scoping report that preceded this file considered, and rejected, a
glob-based sweep over `evals/`, `data/synthetic/`, and `redteam/` for "any phone number that isn't
555-shaped anywhere in the repo." Recording the refusal here so it isn't proposed again: that check has no
self-discovering file list (every new fixture file needs to be added to the glob by hand, the opposite of
what this file is for), and it would need to keep reinventing "what counts as real-shaped" by regex over
free text in arbitrary files -- a differently-shaped synthetic marker (say `999-9999` instead of `555-`)
would silently pass it. It is corpus-wide breadth traded for exactly the kind of hand-maintained brittleness
this file exists to avoid.

**The actual design, and its one honest limit.** `REDACTION_PASSES` (`guardrails/pii.py`, public since this
session for exactly this purpose) is the structural registry -- a category added there is automatically in
this file's scope, the same way a node added to `agents/graph.py`'s `OUTPUT_GUARDRAIL_SOURCES` is
automatically in `redteam/readback_probe.py`'s scope. What is NOT derivable, and `readback_probe.py`'s own
module docstring already names this exact limit for its own `_SITE_PROBES` mapping ("producing a real
`response_text` for a given site needs real domain-shaped inputs... this part cannot be automated away.
What CAN and IS automated is noticing when a probe is missing"): a real, non-synthetic-shaped value per
category cannot be invented by walking the registry, only supplied by hand. This file automates noticing a
missing probe, not inventing one.

Consequently, only categories with a *documented* synthetic-only convention are in scope for the
non-synthetic-probe requirement at all. `OI47` already checked, category by category, which of the eleven
`REDACTION_PASSES` labels even has one:

- The six structured identifiers (`POLICY_NUMBER`/`CLAIM_NUMBER`/`PLATE`/`DRIVERS_LICENCE`/
  `POLICE_REPORT_NUMBER`) are formats this project invents end-to-end -- no real insurer issues them, so
  "synthetic vs. real" doesn't apply. `VIN` is the one structured identifier with a real external format
  (ISO 3779); `OI47` confirmed its correctness directly against that standard, not via a synthetic-marker
  gap -- there is no narrow "this is what our fake VINs look like" convention the way there is for `555`.
- `ADDRESS`/`DATE_TIME`/`LOCATION` are general-purpose language-shape patterns with no synthetic-only
  anchor comparable to `555` -- their honestly-documented limitations (creative phrasing missed) are a
  different, already-disclosed kind of incompleteness.
- `PHONE` (the `555` reserved exchange) and `EMAIL` (`@example.com`/`@email.com`) are the two categories
  `docs/phase0/DOMAIN-ARTIFACTS.md:333`, `docs/phase0/SECURITY-FINDINGS.md:203`, and
  `docs/phase3/DATA-CARD.md:86` all name explicitly as this project's own synthetic-data convention.

`_SYNTHETIC_MARKER` below encodes exactly that split, and `test_categories_with_no_documented_marker_are_
named_not_silently_skipped` asserts every `REDACTION_PASSES` label is classified one way or the other --
so a category added later that nobody classifies fails loudly, rather than silently reading as "not
applicable" by omission.
"""

from __future__ import annotations

from collections.abc import Callable

from fnol_voice_agent.guardrails.pii import REDACTION_PASSES, redact_for_transcript

# Documented synthetic-data markers, sourced from this project's own written policy (cited in the module
# docstring above) -- not derived from code, because there is no code-level registry of "which formats are
# synthetic-only" to derive it from. `None` means: checked against OI47's category analysis, this label has
# no synthetic-only convention to test past, so the non-synthetic-probe requirement below does not apply.
_SYNTHETIC_MARKER: dict[str, Callable[[str], bool] | None] = {
    "POLICY_NUMBER": None,  # invented format, no real analog to generalize against (OI47)
    "CLAIM_NUMBER": None,  # invented format, no real analog to generalize against (OI47)
    "VIN": None,  # real ISO 3779 format; correctness checked directly against the standard, not via a marker
    "PLATE": None,  # invented format, no real analog to generalize against (OI47)
    "DRIVERS_LICENCE": None,  # invented format, no real analog to generalize against (OI47)
    "POLICE_REPORT_NUMBER": None,  # invented format, no real analog to generalize against (OI47)
    "PHONE": lambda s: "555" in s,  # D124/D125's own root cause
    "EMAIL": lambda s: s.rstrip(".,!?").lower().endswith(("@example.com", "@email.com")),
    "ADDRESS": None,  # general-purpose street-shape pattern, no synthetic-only anchor (OI47)
    "DATE_TIME": None,  # general-purpose date/time-shape pattern, no synthetic-only anchor (OI47)
    "LOCATION": None,  # general-purpose location-shape pattern, no synthetic-only anchor (OI47)
}

# Hand-supplied, per the module docstring's limit above -- not derivable, only checkable for absence.
# PHONE and EMAIL values reused from redteam/readback_probe.py's own _PII_PHONE/_PII_EMAIL (ADR-017 Round
# 3's "Free-text PII audit" fixtures) rather than minting new ones a third/fourth time.
_NON_SYNTHETIC_PROBE: dict[str, str] = {
    "PHONE": "416-987-1547",
    "EMAIL": "marcos@gmail.com",
}


def test_every_marked_category_has_a_non_synthetic_probe_registered() -> None:
    """Coverage-gap check, walks `REDACTION_PASSES` -- the registry, not a hand-maintained copy of it. A
    category added later that also gets a `_SYNTHETIC_MARKER` entry but no matching `_NON_SYNTHETIC_PROBE`
    fails HERE, loudly, distinct from whether the pattern itself behaves correctly (checked below). Mirrors
    `redteam/readback_probe.py`'s own coverage-gap design (`report.coverage_gaps`)."""
    marked_labels = {
        label for label, _ in REDACTION_PASSES if _SYNTHETIC_MARKER.get(label) is not None
    }
    missing = marked_labels - set(_NON_SYNTHETIC_PROBE)
    assert (
        not missing
    ), f"category(ies) with a documented synthetic marker but no non-synthetic probe registered: {missing}"


def test_categories_with_no_documented_marker_are_named_not_silently_skipped() -> None:
    """OI47's category-by-category finding, made a live assertion instead of a one-time report: every
    `REDACTION_PASSES` label must appear in `_SYNTHETIC_MARKER`, classified as either a real marker or an
    explicit `None`. A category added to the registry that nobody classifies here fails THIS test -- it
    does not silently read as "not applicable" by omission."""
    registry_labels = {label for label, _ in REDACTION_PASSES}
    unclassified = registry_labels - set(_SYNTHETIC_MARKER)
    assert not unclassified, (
        f"REDACTION_PASSES has categories not classified in _SYNTHETIC_MARKER: {unclassified} -- "
        "classify each as a real synthetic-only marker or an explicit None, per OI47's analysis"
    )


def test_every_registered_probe_is_not_itself_the_synthetic_marker() -> None:
    """Sanity check on the probes themselves: a probe that IS an instance of the marker it's meant to
    demonstrate independence from would make every check below pass for the wrong reason -- catches a
    future copy-paste that reintroduces a 555/example.com-shaped value under a new variable name."""
    for label, probe in _NON_SYNTHETIC_PROBE.items():
        marker = _SYNTHETIC_MARKER[label]
        assert (
            marker is not None
        ), f"{label} has a probe registered but no marker -- remove one or the other"
        assert not marker(
            probe
        ), f"{label}'s own probe {probe!r} IS the synthetic marker it's meant to test past"


def test_every_registered_probe_is_matched_by_its_own_pattern() -> None:
    """The probe must actually match the category's real regex, not merely look real to a human reading
    this file. This is the check `D124` would have caught immediately had it existed before `PHONE_RE` was
    fixed: `"416-987-1547"` against the pre-fix pattern fails here, loudly, the same way it failed in
    `test_pii_redaction.py` and `scripts/verify_log_redaction.py`."""
    patterns = dict(REDACTION_PASSES)
    for label, probe in _NON_SYNTHETIC_PROBE.items():
        assert patterns[label].search(
            probe
        ), f"{label}'s own pattern does not match its non-synthetic probe {probe!r}"


def test_every_registered_probe_is_redacted_through_the_real_public_seam() -> None:
    """Same claim as above, through `redact_for_transcript` -- the actual seam every real caller of this
    module depends on -- rather than the raw compiled pattern in isolation."""
    for label, probe in _NON_SYNTHETIC_PROBE.items():
        text = f"reference value: {probe}"
        redacted = redact_for_transcript(text)
        assert (
            probe not in redacted
        ), f"{label}'s non-synthetic probe {probe!r} leaked into the redacted text"
        assert (
            f"[REDACTED:{label}]" in redacted
        ), f"{label} never fired against its own non-synthetic probe"

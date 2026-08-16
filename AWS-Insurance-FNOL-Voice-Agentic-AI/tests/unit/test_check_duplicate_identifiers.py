"""Negative controls for the duplicate-identifier ledger check (`docs/audits/
2026-08-16-uncommitted-source-audit.md`'s "Fail-loud controls vs. conventions dressed as controls").

Same discipline as `test_check_flows.py`: **the shipped ledger is the fixture, and every violation test
mutates a copy of it into one specific collision.** A guard only ever seen to pass on real content is not
known to work.

One test exists purely about the checker's own reach rather than about the ledger's current content --
`test_cross_reference_mentions_do_not_count_as_duplicate_definitions` -- because the design question this
checker exists to get right is "definition site, not every mention", and a version of this check that
regressed to counting every mention would pass every other test here while being useless in practice (the
real files reference existing identifiers dozens of times each; see the module docstring).
"""

from __future__ import annotations

from pathlib import Path

from scripts.check_duplicate_identifiers import (
    check_project_state,
    check_results,
    find_d_headline_definitions,
    find_oi_row_definitions,
    find_section_headings,
)

PROJECT_STATE_PATH = Path(__file__).resolve().parents[2] / "PROJECT_STATE.md"
RESULTS_PATH = Path(__file__).resolve().parents[2] / "docs" / "RESULTS.md"


# ---------------------------------------------------------------------------------------------------
# The shipped ledger passes. Stated once, so every failure below is a delta from a known-good baseline.
# ---------------------------------------------------------------------------------------------------


def test_the_shipped_project_state_ledger_has_no_duplicate_oi_or_d_identifiers() -> None:
    text = PROJECT_STATE_PATH.read_text(encoding="utf-8")
    assert check_project_state(text) == []


def test_the_shipped_results_doc_has_no_duplicate_section_numbers() -> None:
    text = RESULTS_PATH.read_text(encoding="utf-8")
    assert check_results(text) == []


# ---------------------------------------------------------------------------------------------------
# Duplicate OI row number -- the exact shape of 2026-08-16's collision
# ---------------------------------------------------------------------------------------------------


def test_duplicate_oi_row_number_is_caught() -> None:
    text = PROJECT_STATE_PATH.read_text(encoding="utf-8")
    lines = text.splitlines()
    oi4_line = next(line for line in lines if line.startswith("| OI4 |"))

    # A second, unrelated row reusing OI4 -- same shape as OI12/OI13 being assigned twice on
    # 2026-08-16, just re-created here against OI4 so the test doesn't depend on which OI number is
    # currently free in the live ledger.
    mutated = text + "\n" + oi4_line.replace("`D87`", "`D999`", 1) + "\n"

    violations = check_project_state(mutated)
    assert any("DUPLICATE OI4" in v for v in violations), violations


# ---------------------------------------------------------------------------------------------------
# Duplicate D headline -- two DIFFERENT OI rows both claiming the same D number
# ---------------------------------------------------------------------------------------------------


def test_duplicate_d_headline_across_two_different_oi_rows_is_caught() -> None:
    text = PROJECT_STATE_PATH.read_text(encoding="utf-8")
    lines = text.splitlines()
    oi4_line = next(line for line in lines if line.startswith("| OI4 |"))

    # A new row, its own OI number (no OI collision), but headlining D87 a second time.
    mutated = text + "\n" + oi4_line.replace("| OI4 |", "| OI999 |", 1) + "\n"

    violations = check_project_state(mutated)
    assert any("DUPLICATE D87" in v for v in violations), violations
    assert not any(
        "DUPLICATE OI" in v for v in violations
    ), "this mutation must not also trip the OI check -- OI999 is unique, only D87 collides"


# ---------------------------------------------------------------------------------------------------
# Duplicate RESULTS.md section number
# ---------------------------------------------------------------------------------------------------


def test_duplicate_results_section_number_is_caught() -> None:
    text = RESULTS_PATH.read_text(encoding="utf-8")
    lines = text.splitlines()
    section_45_line = next(line for line in lines if line.startswith("## 45."))

    mutated = text + "\n" + section_45_line + "\n"

    violations = check_results(mutated)
    assert any("DUPLICATE SECTION §45" in v for v in violations), violations


# ---------------------------------------------------------------------------------------------------
# "Found nothing" must fail, not pass -- same principle as check_flows.py's --require-at-least
# ---------------------------------------------------------------------------------------------------


def test_project_state_with_zero_oi_rows_is_a_failure_not_a_silent_pass() -> None:
    violations = check_project_state("# PROJECT_STATE.md\n\nNo Open Items table here at all.\n")
    assert len(violations) == 1
    assert "found zero" in violations[0]


def test_results_with_zero_section_headings_is_a_failure_not_a_silent_pass() -> None:
    violations = check_results("# RESULTS.md\n\nNo numbered sections here at all.\n")
    assert len(violations) == 1
    assert "found zero" in violations[0]


# ---------------------------------------------------------------------------------------------------
# Definition site, not every mention -- the design question this checker exists to get right
# ---------------------------------------------------------------------------------------------------


def test_cross_reference_mentions_do_not_count_as_duplicate_definitions() -> None:
    text = (
        "| # | Item | Status | Closes when |\n"
        "|---|---|---|---|\n"
        "| OI4 | **`D87` — the only row that headlines D87.** Cross-referenced constantly: "
        "`D87`'s hazard, per `D87`, see `D87` again, and `D87` once more for good measure. | OPEN | - |\n"
        "| OI5 | **`D88` — mentions `D87` twice more in its own prose** (`D87` this, `D87` that), "
        "never headlines it. | OPEN | - |\n"
    )
    assert check_project_state(text) == []
    # Sanity: the fixture really does mention D87 six times outside its one legitimate headline --
    # if this drops to 1, the test stopped exercising what it claims to.
    assert text.count("D87") >= 6

    d_defs = find_d_headline_definitions(text)
    assert d_defs == {
        "87": [3],
        "88": [4],
    }  # D87 headlines once (line 3); D88 headlines once (line 4)

    oi_defs = find_oi_row_definitions(text)
    assert oi_defs == {"4": [3], "5": [4]}


def test_section_number_mentioned_in_prose_does_not_count_as_a_heading() -> None:
    text = (
        "## 45. The real section\n\nSome text.\n\n"
        "### A subsection that happens to say 45 in prose, not as its own heading number\n\n"
        "This paragraph mentions §45 and section 45 and `## 45.`-looking text inline, none of which "
        "is a top-level heading.\n\n"
        "## 46. The next real section\n"
    )
    assert check_results(text) == []
    section_defs = find_section_headings(text)
    assert section_defs == {"45": [1], "46": [9]}

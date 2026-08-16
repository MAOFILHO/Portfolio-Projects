"""Reject a commit that assigns the same `D<n>`/`OI<n>` identifier, or the same `docs/RESULTS.md`
top-level section number, to two different entries.

WHY THIS EXISTS

    2026-08-16: two parallel Claude Code sessions, both appending rows to the same shared, uncommitted
    `PROJECT_STATE.md`/`docs/RESULTS.md` ledger, independently assigned `D95`/`OI12` (and separately
    `OI13`) to two unrelated defects. Neither session's tooling noticed; a human reading both threads did.
    Full account in `docs/audits/2026-08-16-uncommitted-source-audit.md`'s "Numbering collision" and
    "Fail-loud controls vs. conventions dressed as controls" sections -- the second of which is *why* this
    script exists rather than a written convention ("claim a block of numbers up front", "re-read the
    ledger before assigning"): a convention that relies on remembering to follow it is not a control, and
    this project already has one precedent for the alternative -- `check_project_root_scope.py`, which
    this check is deliberately modelled on rather than reinvented.

WHAT IT CHECKS

    `PROJECT_STATE.md`'s Open Items table: every row that starts `| OI<n> |` claims that `OI` number, and
    every such row whose content opens `**\\`D<n>\\`` immediately after claims that `D` number as its own
    headline defect. Both claims must be unique across the table.

    `docs/RESULTS.md`: every top-level `## <n>.` (or `## <n>.<n>...`) heading claims that section number.
    Must be unique across the document. Included because it is the same regex-scan mechanism at
    effectively no extra cost, per Marco's own framing of the design question ("if section headings are
    cheap to check, include them") -- not because a section-number collision has actually reached this
    ledger; a sweep at the time this was written found none.

    Deliberately NOT checked: every bare mention of `D<n>`/`OI<n>` in cross-reference prose. Both files
    reference existing identifiers constantly ("`D91`'s hazard realized", "cross-referenced into `OI6`"),
    and a substring match over those would flag nothing real while drowning in noise -- a `git grep`
    sweep run while designing this script found dozens of prose mentions per identifier against usually
    exactly one row that actually OWNS it. Only the row/heading that DEFINES an identifier is checked,
    which is also the only place a genuine collision can occur.

    Fails if it finds ZERO `OI` rows in `PROJECT_STATE.md` or ZERO numbered sections in `RESULTS.md` --
    same principle as `check_flows.py`'s `--require-at-least` and constraint 18's own "finding nothing
    must never read as passing": a regex whose anchor pattern silently stops matching (the table's row
    format changes, the heading style changes) must not present as a clean pass.

GRANDFATHERING A PRE-EXISTING COLLISION

    None exists as of this writing (confirmed by the sweep above), so `GRANDFATHERED_OI`/
    `GRANDFATHERED_D`/`GRANDFATHERED_SECTIONS` are empty. If a genuine pre-existing collision is ever
    found and the fix is deferred rather than immediate, add the specific identifier here -- never in
    advance of the finding, same discipline as `check_project_root_scope.py`'s own `ALLOWLIST` ("add an
    entry only alongside the approval that licenses it"). An entry here silences exactly that one
    identifier for future commits; it does not silence a THIRD row later claiming the same number -- this
    script re-derives "more than one" from the current content every run, it does not cache a count.

RUNS AS

    Appended to the same pre-commit hook as the `PROJECT_ROOT` scope check
    (`scripts/git-hooks/pre-commit`, installed via `make install-hooks`), and as
    `make verify-duplicate-identifiers` for a standalone check against whatever is currently staged.

    Reads the INDEX content of both files (`git show :<path>`), not the working-tree content -- the same
    scope as `check_project_root_scope.py`, and for the same reason: at pre-commit time, a concurrent
    session's own uncommitted, unstaged edits sitting in the same working-tree file are not part of the
    commit under construction, and must not fail it. For a file untouched by the current `git add`, the
    index blob already equals HEAD's blob, so this is a superset of "check what HEAD has," not a
    narrower check.

LIMITATION, STATED RATHER THAN LEFT IMPLICIT

    Bypassable by `git commit --no-verify`, exactly like the `PROJECT_ROOT` hook -- a local hook is a
    backstop for this workspace, not a substitute for a server-side check. No CI-side equivalent exists
    yet. And the row/heading regexes are a description of the ledger's CURRENT formatting convention, not
    a schema -- if that convention drifts (rows stop starting `| OI<n> |`, the `D<n>` headline stops being
    the first backtick token after `**`), this check's `--require-at-least`-style zero-rows failure is the
    only thing standing between that drift and a silent, permanently-clean check.
"""

from __future__ import annotations

import re
import subprocess
import sys

#: This project's own directory, relative to the git repository root -- same constant, same reasoning,
#: as `check_project_root_scope.py`.
PROJECT_ROOT = "AWS-Insurance-FNOL-Voice-Agentic-AI/"

#: Identifiers with a specific, recorded reason a collision was left unresolved rather than fixed
#: immediately. Empty today -- see the module docstring's "Grandfathering" section before adding to any
#: of these.
GRANDFATHERED_OI: frozenset[str] = frozenset()
GRANDFATHERED_D: frozenset[str] = frozenset()
GRANDFATHERED_SECTIONS: frozenset[str] = frozenset()

_OI_ROW_RE = re.compile(r"^\| OI(\d+) \|")
_OI_D_HEADLINE_RE = re.compile(r"^\| OI\d+ \| \*\*`D(\d+)`\s")
_SECTION_HEADING_RE = re.compile(r"^## (\d+(?:\.\d+)*)\.?(?:\s|$)")


def find_oi_row_definitions(text: str) -> dict[str, list[int]]:
    """`OI` number -> 1-based line numbers of every row that starts with it."""
    found: dict[str, list[int]] = {}
    for lineno, line in enumerate(text.splitlines(), start=1):
        match = _OI_ROW_RE.match(line)
        if match:
            found.setdefault(match.group(1), []).append(lineno)
    return found


def find_d_headline_definitions(text: str) -> dict[str, list[int]]:
    """`D` number -> 1-based line numbers of every Open Items row that headlines it. Rows with no
    backtick-`D<n>` immediately after their opening `**` (`OI1`-`OI3`, which predate the `D`-numbering
    scheme) are not in this dict at all -- they make no `D`-number claim to check."""
    found: dict[str, list[int]] = {}
    for lineno, line in enumerate(text.splitlines(), start=1):
        match = _OI_D_HEADLINE_RE.match(line)
        if match:
            found.setdefault(match.group(1), []).append(lineno)
    return found


def find_section_headings(text: str) -> dict[str, list[int]]:
    """Section number, trailing period stripped (`"3"`, `"3.5"`, `"0.0"`) -> 1-based line numbers of
    every top-level `## <n>...` heading that claims it."""
    found: dict[str, list[int]] = {}
    for lineno, line in enumerate(text.splitlines(), start=1):
        match = _SECTION_HEADING_RE.match(line)
        if match:
            found.setdefault(match.group(1), []).append(lineno)
    return found


def _duplicates(defs: dict[str, list[int]], grandfathered: frozenset[str]) -> dict[str, list[int]]:
    return {
        key: lines for key, lines in defs.items() if len(lines) > 1 and key not in grandfathered
    }


def check_project_state(text: str) -> list[str]:
    """Returns violation messages for `PROJECT_STATE.md`'s Open Items table content. Empty list means
    clean. A row-format drift that makes the table invisible to `_OI_ROW_RE` is itself a violation, not a
    silent pass -- see the module docstring."""
    oi_defs = find_oi_row_definitions(text)
    if not oi_defs:
        return [
            "PROJECT_STATE.md: found zero '| OI<n> |' rows. Either the Open Items table is genuinely "
            "empty, or its row format changed and this check can no longer see it -- either way, a check "
            "that inspects nothing must never read as passing."
        ]

    violations: list[str] = []
    for oi, lines in sorted(
        _duplicates(oi_defs, GRANDFATHERED_OI).items(), key=lambda kv: int(kv[0])
    ):
        violations.append(
            f"DUPLICATE OI{oi}: claimed as the row-starting identifier on PROJECT_STATE.md line(s) "
            f"{lines}. Each OI number must own exactly one row."
        )

    d_defs = find_d_headline_definitions(text)
    for d, lines in sorted(_duplicates(d_defs, GRANDFATHERED_D).items(), key=lambda kv: int(kv[0])):
        violations.append(
            f"DUPLICATE D{d}: headlines more than one Open Items row, on PROJECT_STATE.md line(s) "
            f"{lines}. Each D number must have exactly one canonical row."
        )
    return violations


def check_results(text: str) -> list[str]:
    """Returns violation messages for `docs/RESULTS.md`'s top-level section numbering. Empty list means
    clean."""
    section_defs = find_section_headings(text)
    if not section_defs:
        return [
            "docs/RESULTS.md: found zero '## <n>.' top-level section headings. Either the document "
            "genuinely has none, or the heading style changed and this check can no longer see it -- "
            "either way, a check that inspects nothing must never read as passing."
        ]

    violations: list[str] = []
    for section, lines in sorted(
        _duplicates(section_defs, GRANDFATHERED_SECTIONS).items(),
        key=lambda kv: tuple(int(part) for part in kv[0].split(".")),
    ):
        violations.append(
            f"DUPLICATE SECTION §{section}: used as a top-level heading number on docs/RESULTS.md "
            f"line(s) {lines}. Each section number must be used once."
        )
    return violations


def _index_content(relative_path: str) -> str:
    """The content `relative_path` will have in the commit under construction -- the INDEX version,
    which for a file untouched by this commit's `git add` already equals HEAD's blob. See the module
    docstring's "RUNS AS" section for why this, not the working tree, is what gets checked."""
    git_path = f"{PROJECT_ROOT}{relative_path}"
    try:
        result = subprocess.run(
            ["git", "show", f":{git_path}"],
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        raise SystemExit(
            f"check-duplicate-identifiers: could not read staged content of {git_path}: "
            f"{exc.stderr.strip()}"
        ) from exc
    return result.stdout


def main() -> int:
    violations = check_project_state(_index_content("PROJECT_STATE.md"))
    violations += check_results(_index_content("docs/RESULTS.md"))

    if violations:
        print(f"check-duplicate-identifiers: {len(violations)} violation(s):", file=sys.stderr)
        for v in violations:
            print(f" - {v}", file=sys.stderr)
        return 1

    print(
        "check-duplicate-identifiers: ok — no duplicate OI/D identifiers, "
        "no duplicate RESULTS.md section numbers"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

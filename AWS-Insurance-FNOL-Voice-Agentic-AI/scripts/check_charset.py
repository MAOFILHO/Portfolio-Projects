"""Character-set CI check -- no non-Latin-1 characters in strings that reach an AWS API.

Phase 8 Stage 3, `D76`. Runs in `make lint` and in CI, and fails the build rather than warning.

WHY THIS EXISTS

    `aws_iam_role.lex_runtime`'s `description` carried an em dash (U+2014). IAM validates that field
    against

        [\\u0009\\u000A\\u000D\\u0020-\\u007E\\u00A1-\\u00FF]*

    which is Latin-1, and rejected it at `CreateRole` -- as resource 17 of 23, with sixteen already
    created and no rollback. `terraform fmt`, `terraform validate`, `tflint`, `terraform plan` and 488
    unit tests all passed the string first. The value was a plain literal, fully known at plan time, and
    plan still passed it: the provider does not pre-validate string *contents*, only schema. **The first
    thing in the pipeline that looks at this is the AWS API, at apply.** This is that check, moved to the
    front.

    The character class matters more than the one character. U+2014 is what a markdown-shaped writing
    habit produces, but the same range also excludes en dash, curly quotes, ellipsis and arrows -- and,
    less obviously, the non-breaking space (U+00A0), which sits one codepoint below the Latin-1
    supplement's floor and is invisible at any font size. (The soft hyphen, U+00AD, is easy to assume is
    excluded alongside it and is not -- it falls inside U+00A1-U+00FF and IAM accepts it. Checked by
    `test_soft_hyphen_is_within_the_iam_range`, because that assumption was wrong on the first draft of
    this file and a wrong assumption about the boundary is exactly what this check exists to replace.)

SCOPE, AND WHY IT IS A DEFAULT RATHER THAN A LIST

    Every character in every source file under `--root` (default `infra/terraform`) is in scope unless
    something takes it out. There are exactly three ways out, in order of how much they are trusted:

      1. **Comments.** They are not sent anywhere. Detected structurally, per file syntax.
      2. **Terraform-local strings.** An HCL `variable`/`output` block's `description`, and any
         `error_message`, are documentation Terraform renders for humans; they never leave the machine.
         A `default` inside a `variable` block is NOT in this category and is deliberately still checked
         -- `var.greeting`'s default is spoken to a caller through Connect, and `var.hours_time_zone`'s
         reaches the Connect API.
      3. **The exemption registry below**, which requires a stated reason and a stated evidence tier.

    A list of known-bad cases would go stale the first time somebody adds a file. Defaulting to in-scope
    is what makes this a control.

STALE EXEMPTIONS FAIL THE BUILD

    Every registry entry must match at least one real occurrence. An exemption that matches nothing is
    indistinguishable from an exemption that is working, and it silently widens the hole the day the line
    it named is edited. Same failure shape as `check_flows.py`'s `--require-at-least`: a check that finds
    nothing is not a passing check.
"""

from __future__ import annotations

import argparse
import re
import sys
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path


#: The IAM pattern, as a membership test. Tab, LF, CR, printable ASCII, and U+00A1-U+00FF. U+007F (DEL)
#: and U+00A0 (NBSP) are outside it; U+00AD (soft hyphen) is NOT -- it sits inside U+00A1-U+00FF and is
#: accepted despite being invisible. Don't "fix" that without re-reading the module docstring.
def is_latin1_safe(char: str) -> bool:
    codepoint = ord(char)
    return codepoint in (0x09, 0x0A, 0x0D) or 0x20 <= codepoint <= 0x7E or 0xA1 <= codepoint <= 0xFF


#: Extensions worth reading. Everything else under the tree is either binary, generated, or not a source
#: of API-bound literals.
CHECKED_SUFFIXES = frozenset({".tf", ".tftpl", ".tfvars", ".hcl", ".json", ".yaml", ".yml"})

#: Never walked. `.terraform` holds provider binaries; `tfplan` is a generated binary plan file.
SKIP_DIRS = frozenset({".git", ".venv", ".terraform", ".terraform-build", "__pycache__"})
SKIP_NAMES = frozenset({"tfplan", ".terraform.lock.hcl"})


@dataclass(frozen=True)
class Occurrence:
    """One non-Latin-1 character, located."""

    path: Path
    line_number: int
    column: int
    char: str
    line: str

    @property
    def codepoint(self) -> str:
        return f"U+{ord(self.char):04X}"

    @property
    def char_name(self) -> str:
        return unicodedata.name(self.char, "<unnamed>")

    def describe(self, root: Path) -> str:
        return (
            f"{self.path.relative_to(root)}:{self.line_number}:{self.column} "
            f"{self.codepoint} {self.char_name}"
        )


@dataclass(frozen=True)
class Exemption:
    """A permitted non-Latin-1 occurrence, anchored by content rather than by line number.

    `path_suffix` and `line_contains` are both required: a bare substring would exempt the same text
    wherever it later appears, and a bare path would exempt a whole file.

    `indent` is the structural discriminator, and it is the reason this registry is honest rather than
    approximately honest. In `bot.yaml.tftpl` a slot's `Description:` and an intent's `Description:` are
    the same eleven characters; only their nesting tells them apart -- slots sit at 18, intents at 14.
    Matching on the substring alone would have exempted intent Descriptions under a measurement that
    covers only slots. Anchoring on indentation is brittle to reformatting, deliberately: a reformat
    makes the exemption match nothing, and a stale exemption FAILS the build. It breaks toward noticing.

    `evidence` is not decoration. It records *how strongly* the exemption is backed, because the two
    entries here are backed very differently and collapsing that distinction is how a measured fact and
    an assumption end up cited identically.
    """

    path_suffix: str
    line_contains: str
    codepoint: str
    reason: str
    evidence: str
    indent: int | None = None
    matched: list[Occurrence] = field(default_factory=list, compare=False)

    def covers(self, occurrence: Occurrence) -> bool:
        if self.indent is not None:
            actual = len(occurrence.line) - len(occurrence.line.lstrip())
            if actual != self.indent:
                return False
        return (
            occurrence.path.as_posix().endswith(self.path_suffix)
            and self.line_contains in occurrence.line
            and occurrence.codepoint == self.codepoint
        )


def build_registry() -> list[Exemption]:
    """The exemption registry. Two entries, backed by two different kinds of evidence.

    Adding a third is a decision, not a fix. If a build fails here, the first question is whether the
    string needs the character at all -- both entries below needed it for a reason that survives being
    written down, and most strings do not.
    """
    return [
        Exemption(
            path_suffix="stacks/main/bot.yaml.tftpl",
            line_contains='Value: "Which would you like to update',
            codepoint="U+2014",
            indent=30,
            reason=(
                "Caller-spoken content, not an identifier. This string is synthesised by Polly and read "
                "to a human; the em dash is a prosodic pause in a three-item question. Replacing it with "
                "a hyphen or a semicolon would change what a caller hears, which is a behaviour change "
                "smuggled in as a lint fix. If this ever has to move, it moves as a dialogue decision "
                "with SLOT-DESIGN.md, not as a character swap."
            ),
            evidence=(
                "MEASURED (adjacent). Lex V2 accepts U+2014 in this template through the same CFN path "
                "-- see the slot Description entry. Message values carry no documented Pattern at all "
                "and are the least constrained field in the bot definition."
            ),
        ),
        Exemption(
            path_suffix="bot.yaml.tftpl",
            line_contains="Description:",
            codepoint="U+2014",
            # 18 is a SLOT's Description. An intent's sits at 14 and is NOT covered here -- see below.
            indent=18,
            reason=(
                "Lex V2 slot Description. `CreateSlot`'s reference documents a length constraint (0-200) "
                "and no Pattern, and unlike the IAM case that is corroborated by an apply rather than "
                "trusted on its own."
            ),
            evidence=(
                "MEASURED. `infra/terraform/stacks/lexpoc/bot.yaml.tftpl` carried U+2014 in three slot "
                "Description fields (`policy_number`, `loss_datetime`, `police_report_number`) and "
                "applied successfully THREE TIMES against live Lex V2 in Phase 8 Stage 2 -- create, "
                "update, and delete-propagation. Recorded in docs/phase8/LEXPOC-GATE.md. This is the "
                "only field in this project measured to accept a character outside Latin-1. "
                "NOT extended to intent Description: Stage 2's POC carried no em dash in one, so there "
                "is no measurement to cite, and the one that existed (`RentalTowingEntitlement`) was "
                "rewritten rather than exempted on an assumption."
            ),
        ),
    ]


# ---------------------------------------------------------------------------------------------------
# Classification: which lines are out of scope, and why
# ---------------------------------------------------------------------------------------------------

_HCL_TOP_LEVEL_LOCAL_BLOCK = re.compile(r'^(variable|output)\s+"')
_HEREDOC_OPEN = re.compile(r"<<-?([A-Za-z_][A-Za-z0-9_]*)\s*$")
_LOCAL_ASSIGNMENT = re.compile(r"^\s*(description|error_message)\s*=")


def hcl_out_of_scope_lines(text: str) -> set[int]:
    """1-indexed line numbers in a `.tf` file that cannot reach an AWS API.

    Two categories: comments, and documentation strings inside a top-level `variable` or `output` block.

    Block tracking leans on a guarantee this repo already enforces -- `terraform fmt` is checked in CI,
    so a top-level block always opens at column 0 and its closing brace is a `}` at column 0. That makes
    the scan reliable without an HCL parser, and it fails safe: if fmt ever stops running, blocks stop
    being recognised and MORE lines are checked, not fewer.

    `default` is deliberately absent from `_LOCAL_ASSIGNMENT`. A variable's default is a value, and this
    project's defaults include the greeting a caller hears and the time zone sent to Connect.
    """
    out_of_scope: set[int] = set()
    lines = text.split("\n")

    in_block_comment = False
    in_local_block = False
    heredoc_terminator: str | None = None
    heredoc_is_local = False

    for index, line in enumerate(lines):
        line_number = index + 1

        # A heredoc body is opaque to every other rule -- `#` inside one is text, not a comment.
        if heredoc_terminator is not None:
            if heredoc_is_local:
                out_of_scope.add(line_number)
            if line.strip() == heredoc_terminator:
                heredoc_terminator = None
            continue

        if in_block_comment:
            out_of_scope.add(line_number)
            if "*/" in line:
                in_block_comment = False
            continue

        stripped = line.strip()

        if stripped.startswith("/*"):
            out_of_scope.add(line_number)
            if "*/" not in stripped:
                in_block_comment = True
            continue

        if stripped.startswith("#") or stripped.startswith("//"):
            out_of_scope.add(line_number)
            continue

        if _HCL_TOP_LEVEL_LOCAL_BLOCK.match(line):
            in_local_block = True
        elif line.startswith("}"):
            in_local_block = False

        is_local_assignment = in_local_block and bool(_LOCAL_ASSIGNMENT.match(line))

        heredoc = _HEREDOC_OPEN.search(line)
        if heredoc is not None:
            heredoc_terminator = heredoc.group(1)
            heredoc_is_local = is_local_assignment

        if is_local_assignment:
            out_of_scope.add(line_number)

    return out_of_scope


def hash_comment_lines(text: str) -> set[int]:
    """1-indexed comment line numbers for YAML, JSON-with-comments and template files.

    Only whole-line comments count. A trailing `#` inside a YAML value is not a comment, and guessing
    where a quoted string ends without a parser would be the kind of approximation that makes a check
    silently permissive.
    """
    return {
        index + 1 for index, line in enumerate(text.split("\n")) if line.strip().startswith("#")
    }


def out_of_scope_lines(path: Path, text: str) -> set[int]:
    if path.suffix in (".tf", ".tfvars", ".hcl"):
        return hcl_out_of_scope_lines(text)
    return hash_comment_lines(text)


# ---------------------------------------------------------------------------------------------------
# Scanning
# ---------------------------------------------------------------------------------------------------


def source_files(root: Path) -> list[Path]:
    return sorted(
        path
        for path in root.rglob("*")
        if path.is_file()
        and path.suffix in CHECKED_SUFFIXES
        and path.name not in SKIP_NAMES
        and not any(part in SKIP_DIRS for part in path.parts)
    )


def scan_file(path: Path, text: str) -> list[Occurrence]:
    """Every in-scope non-Latin-1 character in one file."""
    skip = out_of_scope_lines(path, text)
    found: list[Occurrence] = []

    for index, line in enumerate(text.split("\n")):
        line_number = index + 1
        if line_number in skip:
            continue
        for column, char in enumerate(line, start=1):
            if not is_latin1_safe(char):
                found.append(Occurrence(path, line_number, column, char, line))

    return found


def scan(root: Path) -> tuple[list[Occurrence], int]:
    """All in-scope occurrences under `root`, and the number of files read."""
    occurrences: list[Occurrence] = []
    files = source_files(root)

    for path in files:
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        occurrences.extend(scan_file(path, text))

    return occurrences, len(files)


def partition(
    occurrences: list[Occurrence], registry: list[Exemption]
) -> tuple[list[Occurrence], list[Exemption]]:
    """Split occurrences into violations and exempted, recording what each exemption matched."""
    violations: list[Occurrence] = []

    for occurrence in occurrences:
        covering = next((e for e in registry if e.covers(occurrence)), None)
        if covering is None:
            violations.append(occurrence)
        else:
            covering.matched.append(occurrence)

    return violations, registry


def applicable_exemptions(registry: list[Exemption], files: list[Path]) -> list[Exemption]:
    """Registry entries whose named file actually exists under the scanned root.

    Staleness is only meaningful in scope: `--root` narrower than the full tree (a single stack, a test
    fixture) legitimately contains none of `bot.yaml.tftpl` or `release.yaml.tftpl`, and that must read as
    "not applicable here", not as "the exemption stopped working". A file that IS present but no longer
    produces the exemption's match is the real staleness signal -- something changed underneath it.
    """
    return [
        exemption
        for exemption in registry
        if any(f.as_posix().endswith(exemption.path_suffix) for f in files)
    ]


# ---------------------------------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Fail the build on non-Latin-1 characters in strings that reach an AWS API."
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "infra" / "terraform",
        help=(
            "Tree to walk. Defaults to infra/terraform, where this project's API-bound string literals "
            "are declared."
        ),
    )
    parser.add_argument(
        "--require-at-least",
        type=int,
        default=10,
        help=(
            "Fail if fewer than this many source files were read. A checker pointed at the wrong "
            "directory examines nothing and passes, which is indistinguishable from a clean tree."
        ),
    )
    args = parser.parse_args(argv)
    root = args.root.resolve()

    if not root.is_dir():
        print(f"check-charset: FAILED -- {root} is not a directory.", file=sys.stderr)
        return 1

    files = source_files(root)
    occurrences, file_count = scan(root)
    violations, registry = partition(occurrences, build_registry())

    print(f"check-charset: {file_count} source file(s) read under {root}")

    if file_count < args.require_at_least:
        print(
            f"check-charset: FAILED -- read {file_count} files, expected at least "
            f"{args.require_at_least}. A check that examines nothing is not a passing check.",
            file=sys.stderr,
        )
        return 1

    failed = False

    stale = [e for e in applicable_exemptions(registry, files) if not e.matched]
    if stale:
        failed = True
        print("  FAIL stale exemption(s) -- each matched nothing:")
        for exemption in stale:
            print(
                f"       {exemption.path_suffix} :: {exemption.line_contains!r} :: {exemption.codepoint}"
            )
        print(
            "       An exemption that matches nothing looks identical to one that is working, and it "
            "widens\n"
            "       silently the day the line it named is edited. Re-anchor it or delete it."
        )

    for exemption in registry:
        if exemption.matched:
            print(
                f"  exempt {exemption.path_suffix} :: {exemption.codepoint} "
                f"({len(exemption.matched)} occurrence(s)) -- {exemption.evidence.split('.')[0]}"
            )

    if violations:
        failed = True
        print(f"  FAIL {len(violations)} non-Latin-1 character(s) in in-scope strings:")
        for occurrence in violations:
            print(f"       {occurrence.describe(root)}")
            print(f"           {occurrence.line.strip()[:110]}")
        print(
            "\n       These reach an AWS API. IAM rejects them outright; other services are unmeasured,\n"
            "       and unmeasured is the state D76 was in the day the apply died at resource 17 of 23.\n"
            "       Replace the character, or add a registry entry to scripts/check_charset.py with a\n"
            "       reason and an evidence tier."
        )

    if not failed:
        print("  ok   no non-Latin-1 characters in in-scope strings")

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

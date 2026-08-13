"""Character-set CI check -- no non-ASCII/non-Latin-1 characters in strings that reach an AWS API.

Phase 8 Stage 3, `D76` and `D77`. Runs in `make lint` and in CI, and fails the build rather than warning.

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

`D77` -- THE REGISTRY THAT USED TO BE HERE WAS WRONG, AND HOW THAT WAS FOUND

    The first version of this file shipped two exemptions, both marked "MEASURED": a Lex slot
    `Description` and a caller-spoken message value, both citing Stage 2's lexpoc applies as evidence that
    Lex V2 accepts U+2014 through the nested-CFN path. Both claims were **wrong**, and wrong in a specific,
    instructive way: "the apply did not error" was read as "the character survived", and those are not the
    same fact. `CreateStack` does not reject non-ASCII in `template_body` outright -- it silently replaces
    every byte above U+007E with `?` and returns success. Confirmed against AWS's own stored copy, not
    Terraform's cache: a live `aws cloudformation get-template --template-stage Original` on the deployed
    `fnol-bot` stack showed every em dash AND every section sign (`§`, inside Latin-1, previously
    judged safe by this exact file) rendered as `?`. Terraform's next plan then showed a perpetual,
    content-only "update" to `aws_cloudformation_stack.bot` -- not a rejection, a silent, permanent drift
    between what the source declares and what the service actually stored.

    This is `RESULTS.md` section 3.5.1's family again, in a new shape: not a build that finishes after the
    control plane reports success, but a **value** that is silently substituted while the control plane
    reports success. And it is `D69` again too -- "count the instruments before trusting the one you
    wrote" -- because the instrument that was trusted was "did the apply error", and the disagreeing
    instrument, once someone thought to ask it, was `GetTemplate` read straight from the service.

    Consequence: `bot.yaml.tftpl` and `release.yaml.tftpl` are now plain ASCII throughout, comments
    included -- CloudFormation receives the whole file as `template_body`, so a comment is not "never
    sent anywhere" for these two files the way it is for an ordinary `.tf` file. The registry below is
    empty as a result. It stays in the file as working infrastructure rather than being deleted, because
    the *mechanism* -- an evidence-tiered, content-anchored, staleness-checked exemption -- is still the
    right shape for some future field that is genuinely measured against a live read-back. What changed
    is the bar: "the apply did not error" no longer qualifies as MEASURED for anything CFN-shaped. A
    future entry needs a `GetTemplate`, `DescribeSlot`, or equivalent read against the live service.

SCOPE, AND WHY IT IS A DEFAULT RATHER THAN A LIST

    Every character in every source file under `--root` (default `infra/terraform`) is in scope unless
    something takes it out. There are exactly three ways out, in order of how much they are trusted:

      1. **Comments -- in files that are NOT a CFN template source.** They are not sent anywhere. Detected
         structurally, per file syntax. For `bot.yaml.tftpl` and `release.yaml.tftpl` this carve-out does
         NOT apply -- see CFN_TEMPLATE_BASENAMES below. The whole file is the request body.
      2. **Terraform-local strings.** An HCL `variable`/`output` block's `description`, and any
         `error_message`, are documentation Terraform renders for humans; they never leave the machine.
         A `default` inside a `variable` block is NOT in this category and is deliberately still checked
         -- `var.greeting`'s default is spoken to a caller through Connect, and `var.hours_time_zone`'s
         reaches the Connect API.
      3. **The exemption registry below**, which requires a stated reason and a stated evidence tier --
         and, per `D77`, a live read-back for anything that is CFN-shaped.

    A list of known-bad cases would go stale the first time somebody adds a file. Defaulting to in-scope
    is what makes this a control.

TWO RULES, NOT ONE

    Everything under `--root` is checked against `is_latin1_safe` (IAM's actual documented pattern) EXCEPT
    files named in `CFN_TEMPLATE_BASENAMES`, which are checked against the strictly narrower
    `is_ascii_safe`. That narrowing is itself evidence-based -- `D77`'s live `GetTemplate` read -- and it
    is a **tightening**, not a loosening, so it does not need the same justification machinery as the
    exemption registry: the registry exists to permit exceptions to the default; this exists to protect
    two specific files from a default that is documented but, for them, empirically wrong.

STALE EXEMPTIONS FAIL THE BUILD

    Every registry entry must match at least one real occurrence, among files that are in scope for it.
    An exemption that matches nothing is indistinguishable from an exemption that is working, and it
    silently widens the hole the day the line it named is edited. Same failure shape as
    `check_flows.py`'s `--require-at-least`: a check that finds nothing is not a passing check.
"""

from __future__ import annotations

import argparse
import re
import sys
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path


#: The IAM pattern, as a membership test. Tab, LF, CR, printable ASCII, and U+00A1-U+00FF. U+007F (DEL)
#: and U+00A0 (NBSP) are outside it; U+00AD (soft hyphen) is NOT -- it sits inside U+00A1-U+00FF and is
#: accepted despite being invisible. Don't "fix" that without re-reading the module docstring.
def is_latin1_safe(char: str) -> bool:
    codepoint = ord(char)
    return codepoint in (0x09, 0x0A, 0x0D) or 0x20 <= codepoint <= 0x7E or 0xA1 <= codepoint <= 0xFF


#: Strictly narrower than `is_latin1_safe`: drops the whole U+00A1-U+00FF Latin-1 supplement, including
#: the section sign that `D77` found CloudFormation silently mangles to `?` despite it being inside the
#: IAM-documented range. Applied only to `CFN_TEMPLATE_BASENAMES`.
def is_ascii_safe(char: str) -> bool:
    codepoint = ord(char)
    return codepoint in (0x09, 0x0A, 0x0D) or 0x20 <= codepoint <= 0x7E


#: Files whose ENTIRE content -- comments included -- becomes an `aws_cloudformation_stack.template_body`
#: (see `infra/terraform/stacks/*/lex.tf`'s `templatefile()` locals). Matched by basename, not by path, so
#: `stacks/lexpoc`'s copy is covered too: same mechanism, same measured failure mode, even though that
#: stack is destroyed and the file is historical. A new file playing this role must be added here --
#: nothing in this checker can discover the CFN wiring in `lex.tf` on its own, so this list is manually
#: maintained the same way `build_registry()` is, and for the same reason: an addition here is a decision,
#: not an automatic inference.
CFN_TEMPLATE_BASENAMES = frozenset({"bot.yaml.tftpl", "release.yaml.tftpl"})


#: Extensions worth reading. Everything else under the tree is either binary, generated, or not a source
#: of API-bound literals.
CHECKED_SUFFIXES = frozenset({".tf", ".tftpl", ".tfvars", ".hcl", ".json", ".yaml", ".yml"})

#: Never walked. `.terraform` holds provider binaries; `tfplan` is a generated binary plan file.
SKIP_DIRS = frozenset({".git", ".venv", ".terraform", ".terraform-build", "__pycache__"})
SKIP_NAMES = frozenset({"tfplan", ".terraform.lock.hcl"})


def safety_check_for(path: Path) -> tuple[str, Callable[[str], bool]]:
    """The (rule name, predicate) pair that applies to one file."""
    if path.name in CFN_TEMPLATE_BASENAMES:
        return "ASCII", is_ascii_safe
    return "Latin-1", is_latin1_safe


@dataclass(frozen=True)
class Occurrence:
    """One character rejected by the rule that applies to its file, located."""

    path: Path
    line_number: int
    column: int
    char: str
    line: str
    rule_name: str

    @property
    def codepoint(self) -> str:
        return f"U+{ord(self.char):04X}"

    @property
    def char_name(self) -> str:
        return unicodedata.name(self.char, "<unnamed>")

    def describe(self, root: Path) -> str:
        return (
            f"{self.path.relative_to(root)}:{self.line_number}:{self.column} "
            f"{self.codepoint} {self.char_name} (outside {self.rule_name})"
        )


@dataclass(frozen=True)
class Exemption:
    """A permitted out-of-rule occurrence, anchored by content rather than by line number.

    `path_suffix` and `line_contains` are both required: a bare substring would exempt the same text
    wherever it later appears, and a bare path would exempt a whole file.

    `indent` is a structural discriminator for cases like `bot.yaml.tftpl`, where a slot's `Description:`
    and an intent's `Description:` are the same eleven characters and only nesting tells them apart --
    slots sit at 18, intents at 14. Anchoring on indentation is brittle to reformatting, deliberately: a
    reformat makes the exemption match nothing, and a stale exemption FAILS the build. It breaks toward
    noticing.

    `evidence` is not decoration. Per `D77`, an exemption for a file in `CFN_TEMPLATE_BASENAMES` needs a
    live read-back (`GetTemplate`, `DescribeSlot`, ...), not "the apply did not error" -- that bar is
    exactly what the previous registry got wrong, at this project's own expense.
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
    """The exemption registry. Empty by design -- see `D77` in the module docstring.

    The two entries this file shipped with originally were both retracted: their "MEASURED" evidence was
    an apply that did not error, and `D77` found that CloudFormation accepts a non-ASCII `template_body`
    without erroring while silently replacing every offending byte with `?`. Neither exemption's
    character actually reached Lex intact. Both strings were rewritten to plain ASCII instead of being
    re-exempted, because the honest evidence bar for a CFN-shaped field is a live read-back, and neither
    had one.

    Adding an entry here is a decision, not a fix. If a build fails here, the first question is whether
    the string needs the character at all -- almost none do. If one genuinely does, back it with a read
    against the live service, not an apply's exit code.
    """
    return []


# ---------------------------------------------------------------------------------------------------
# Classification: which lines are out of scope, and why
# ---------------------------------------------------------------------------------------------------

_HCL_TOP_LEVEL_LOCAL_BLOCK = re.compile(r'^(variable|output)\s+"')
_HEREDOC_OPEN = re.compile(r"<<-?([A-Za-z_][A-Za-z0-9_]*)\s*$")
_LOCAL_ASSIGNMENT = re.compile(r"^\s*(description|error_message)\s*=")


def hcl_out_of_scope_lines(text: str) -> set[int]:
    """1-indexed line numbers in a `.tf` file that cannot reach an AWS API.

    Two categories: comments, and documentation strings inside a top-level `variable` or `output` block.
    Never applied to a `CFN_TEMPLATE_BASENAMES` file -- those have no out-of-scope lines at all, comments
    included, because the whole file is submitted as `template_body`.

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


def out_of_scope_lines(path: Path, text: str) -> set[int]:
    """Lines exempt from scanning for one file. Empty set for any `CFN_TEMPLATE_BASENAMES` file -- see
    `hcl_out_of_scope_lines`'s docstring."""
    if path.name in CFN_TEMPLATE_BASENAMES:
        return set()
    if path.suffix in (".tf", ".tfvars", ".hcl"):
        return hcl_out_of_scope_lines(text)
    return {
        index + 1 for index, line in enumerate(text.split("\n")) if line.strip().startswith("#")
    }


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
    """Every in-scope out-of-rule character in one file, under whichever rule applies to it."""
    skip = out_of_scope_lines(path, text)
    rule_name, is_safe = safety_check_for(path)
    found: list[Occurrence] = []

    for index, line in enumerate(text.split("\n")):
        line_number = index + 1
        if line_number in skip:
            continue
        for column, char in enumerate(line, start=1):
            if not is_safe(char):
                found.append(Occurrence(path, line_number, column, char, line, rule_name))

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
        description=(
            "Fail the build on non-Latin-1 characters in AWS-API-bound strings (non-ASCII for files "
            "that become a CloudFormation template_body -- see D77)."
        )
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

    cfn_scanned = sorted({f.name for f in files if f.name in CFN_TEMPLATE_BASENAMES})
    if cfn_scanned:
        print(f"  strict ASCII rule applied to: {', '.join(cfn_scanned)} (D77)")

    if violations:
        failed = True
        print(f"  FAIL {len(violations)} out-of-rule character(s) in in-scope strings:")
        for occurrence in violations:
            print(f"       {occurrence.describe(root)}")
            print(f"           {occurrence.line.strip()[:110]}")
        print(
            "\n       These reach an AWS API. IAM rejects Latin-1 violations outright; CloudFormation "
            "template_body\n"
            "       (bot.yaml.tftpl, release.yaml.tftpl) SILENTLY MANGLES anything outside plain ASCII "
            "to '?'\n"
            "       instead of rejecting it (D77) -- do not assume a clean apply means the character "
            "survived.\n"
            "       Replace the character, or add a registry entry to scripts/check_charset.py backed "
            "by a live\n"
            "       read-back, not an apply's exit code."
        )

    if not failed:
        print("  ok   no out-of-rule characters in in-scope strings")

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

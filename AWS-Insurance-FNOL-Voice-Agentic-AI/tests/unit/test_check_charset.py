"""Negative controls for the character-set CI check.

Phase 8 Stage 3, `D76`. Same discipline as `test_check_flows.py`: every failure case is a fixture built
to trigger one specific rule, and the shipped tree is exercised directly rather than only in miniature —
`test_the_shipped_tree_is_clean` is the thing that would have caught the original em dash.
"""

from __future__ import annotations

from pathlib import Path

from scripts.check_charset import (
    Exemption,
    build_registry,
    hcl_out_of_scope_lines,
    is_latin1_safe,
    main,
    partition,
    scan,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
INFRA_ROOT = REPO_ROOT / "infra" / "terraform"


# ---------------------------------------------------------------------------------------------------
# The shipped tree passes, with the current registry. Stated once so every failure below is a delta.
# ---------------------------------------------------------------------------------------------------


def test_the_shipped_tree_is_clean() -> None:
    occurrences, file_count = scan(INFRA_ROOT)
    violations, registry = partition(occurrences, build_registry())
    assert file_count >= 10, "scanned suspiciously few files -- is --root pointed correctly?"
    assert violations == []
    assert all(e.matched for e in registry), "an exemption in the shipped registry matched nothing"


def test_main_exits_zero_on_the_real_tree() -> None:
    assert main(["--root", str(INFRA_ROOT)]) == 0


# ---------------------------------------------------------------------------------------------------
# is_latin1_safe -- the IAM pattern itself, boundary by boundary
# ---------------------------------------------------------------------------------------------------


def test_ascii_printable_is_safe() -> None:
    assert all(is_latin1_safe(chr(c)) for c in range(0x20, 0x7F))


def test_tab_lf_cr_are_safe() -> None:
    assert is_latin1_safe("\t")
    assert is_latin1_safe("\n")
    assert is_latin1_safe("\r")


def test_del_is_not_safe() -> None:
    """U+007F sits one past the printable-ASCII ceiling IAM's pattern actually uses."""
    assert not is_latin1_safe("\x7f")


def test_latin1_supplement_above_nbsp_is_safe() -> None:
    assert is_latin1_safe("\xa1")  # ¡, the range's floor
    assert is_latin1_safe("\xff")  # ÿ, the range's ceiling


def test_nbsp_is_not_safe() -> None:
    """U+00A0, the character directly below the range IAM accepts. The off-by-one this range invites."""
    assert not is_latin1_safe("\xa0")


def test_soft_hyphen_is_within_the_iam_range() -> None:
    """The opposite of the intuitive answer: U+00AD sits inside U+00A1-U+00FF and IAM accepts it,
    invisible as it is. `is_latin1_safe` must match the literal pattern, not the intuition about it --
    the module docstring names this explicitly because it was the wrong assumption on the first draft.
    """
    assert is_latin1_safe("\xad")


def test_em_dash_is_not_safe() -> None:
    """The character that actually broke the apply."""
    assert not is_latin1_safe("—")


# ---------------------------------------------------------------------------------------------------
# The default is in-scope. A fresh file with an em dash fails with no exemption written for it.
# ---------------------------------------------------------------------------------------------------


def test_a_new_file_with_an_em_dash_fails_by_default(tmp_path: Path) -> None:
    (tmp_path / "new.tf").write_text(
        'resource "aws_iam_role" "example" {\n'
        '  description = "Runtime role — nothing exempts this."\n'
        "}\n",
        encoding="utf-8",
    )
    assert main(["--root", str(tmp_path), "--require-at-least", "1"]) == 1


def test_a_clean_new_file_passes(tmp_path: Path) -> None:
    (tmp_path / "new.tf").write_text(
        'resource "aws_iam_role" "example" {\n'
        '  description = "Runtime role; nothing exotic here."\n'
        "}\n",
        encoding="utf-8",
    )
    assert main(["--root", str(tmp_path), "--require-at-least", "1"]) == 0


# ---------------------------------------------------------------------------------------------------
# hcl_out_of_scope_lines -- the three carve-outs, and that `default` is NOT one of them
# ---------------------------------------------------------------------------------------------------


def test_comment_lines_are_out_of_scope() -> None:
    text = '# a comment with an em dash — right here\nresource "x" "y" {}\n'
    assert hcl_out_of_scope_lines(text) == {1}


def test_variable_description_is_out_of_scope() -> None:
    text = (
        'variable "greeting" {\n'
        '  description = "Local doc only — never reaches AWS."\n'
        '  default     = "Hello."\n'
        "}\n"
    )
    assert hcl_out_of_scope_lines(text) == {2}


def test_variable_default_is_in_scope() -> None:
    """The line this test guards is the one a careless version of this checker would have missed:
    `var.greeting`'s default is spoken to a caller through Connect, and `var.hours_time_zone`'s default
    is sent to the Connect API. Neither is documentation."""
    text = (
        'variable "greeting" {\n'
        '  description = "doc"\n'
        '  default     = "Hi there — an em dash a careless exemption would miss."\n'
        "}\n"
    )
    assert hcl_out_of_scope_lines(text) == {2}


def test_error_message_is_out_of_scope() -> None:
    text = (
        'variable "bot_name" {\n'
        "  validation {\n"
        '    error_message = "must match ^[a-z]+$ — see the pattern."\n'
        "  }\n"
        "}\n"
    )
    assert hcl_out_of_scope_lines(text) == {3}


def test_heredoc_description_is_out_of_scope() -> None:
    text = (
        'variable "greeting" {\n'
        "  description = <<-EOT\n"
        "    Multi-line doc with an em dash — still local.\n"
        "  EOT\n"
        '  default     = "Hi."\n'
        "}\n"
    )
    assert hcl_out_of_scope_lines(text) == {2, 3, 4}


def test_non_local_block_is_not_exempted() -> None:
    """A resource block's `description` is not a `variable`/`output` block and must stay in scope."""
    text = (
        'resource "aws_iam_role" "example" {\n'
        '  description = "Role description — reaches IAM, not exempt."\n'
        "}\n"
    )
    assert hcl_out_of_scope_lines(text) == set()


# ---------------------------------------------------------------------------------------------------
# Exemption.covers -- structural anchoring, and stale-exemption detection
# ---------------------------------------------------------------------------------------------------


def test_stale_exemption_fails_the_build_when_its_file_is_in_scope(tmp_path: Path) -> None:
    """An exemption is only as trustworthy as its last confirmed match. If its named file is in scope
    but no longer produces the match -- the text moved, the character was removed, the indent changed --
    the build must say so rather than silently carry a hole nobody is using."""
    (tmp_path / "bot.yaml.tftpl").write_text(
        'Description: "no em dash here anymore"\n', encoding="utf-8"
    )

    from scripts import check_charset

    original = check_charset.build_registry
    try:
        check_charset.build_registry = lambda: [  # type: ignore[assignment]
            Exemption(
                path_suffix="bot.yaml.tftpl",
                line_contains="never matches this file's actual content",
                codepoint="U+2014",
                reason="test fixture",
                evidence="test fixture",
            )
        ]
        assert main(["--root", str(tmp_path), "--require-at-least", "1"]) == 1
    finally:
        check_charset.build_registry = original  # type: ignore[assignment]


def test_exemption_for_an_out_of_scope_file_is_not_stale(tmp_path: Path) -> None:
    """The inverse: `--root` narrower than the full tree (a single stack, this very fixture) legitimately
    contains none of `bot.yaml.tftpl`. That must read as 'not applicable here', not as 'broken exemption'
    -- otherwise every scoped or partial invocation of this checker fails on files it never looked at.
    """
    (tmp_path / "clean.tf").write_text(
        'resource "x" "y" {\n  description = "fine"\n}\n', encoding="utf-8"
    )
    assert main(["--root", str(tmp_path), "--require-at-least", "1"]) == 0


def test_indent_anchored_exemption_does_not_cover_a_different_indent() -> None:
    """The slot-vs-intent case in bot.yaml.tftpl: identical field name, different nesting, and an
    exemption measured for one must not silently cover the other."""
    exemption = Exemption(
        path_suffix="bot.yaml.tftpl",
        line_contains="Description:",
        codepoint="U+2014",
        reason="test",
        evidence="test",
        indent=18,
    )

    from scripts.check_charset import Occurrence

    slot_line = '                  Description: "slot text — em dash"'
    intent_line = '              Description: "intent text — em dash"'
    assert len(slot_line) - len(slot_line.lstrip()) == 18
    assert len(intent_line) - len(intent_line.lstrip()) == 14

    slot_occurrence = Occurrence(Path("x/bot.yaml.tftpl"), 1, 30, "—", slot_line)
    intent_occurrence = Occurrence(Path("x/bot.yaml.tftpl"), 1, 30, "—", intent_line)

    assert exemption.covers(slot_occurrence)
    assert not exemption.covers(intent_occurrence)


def test_exemption_does_not_cross_files() -> None:
    exemption = build_registry()[1]  # the slot-Description exemption, path_suffix="bot.yaml.tftpl"
    from scripts.check_charset import Occurrence

    line = '                  Description: "text — em dash"'
    unrelated = Occurrence(Path("infra/terraform/stacks/main/lex.tf"), 1, 10, "—", line)
    assert not exemption.covers(unrelated)

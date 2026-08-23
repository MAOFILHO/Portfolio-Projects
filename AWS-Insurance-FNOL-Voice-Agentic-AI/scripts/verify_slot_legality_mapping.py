"""`D162`/`OI80` fix, exit-criteria table row 3 (`PROJECT_STATE.md`) -- the derived `bot.yaml.tftpl`
legal-slot-name mapping.

STANDALONE, NOT YET WIRED INTO `_elicit_slot`. This module exists so rows 1/2 (the guard inside
`api/lex_codehook.py::_elicit_slot`) have a derived source of truth to import instead of hand-duplicating
it a second time -- mirroring `_SLOT_BEARING_INTENTS`'s own comment, which already accepts that exact
duplication risk for intent *names* and is the thing this row exists not to repeat for slot *names*.
Nothing in `src/` imports this module yet; that wiring is rows 1/2's own scope, per the approved
exit-criteria table ("Do NOT touch `_elicit_slot` yet").

WHY NOT PLAIN `yaml.safe_load`
    `bot.yaml.tftpl` is CloudFormation YAML (nested inside `aws_cloudformation_stack`, `ADR-007`), not
    plain YAML: it uses CloudFormation's short-form intrinsic-function tags (`!Ref`, `!GetAtt`), which
    `yaml.safe_load` has no constructor for and raises on -- confirmed directly, not assumed:
    `yaml.safe_load(bot.yaml.tftpl's text)` raises `yaml.constructor.ConstructorError: could not
    determine a constructor for the tag '!Ref'` at the file's own `Outputs:` block
    (`infra/terraform/stacks/main/bot.yaml.tftpl:849`, `Value: !Ref FnolBot`) -- also used at `:66-67`,
    `:88`, `:852`.

    Terraform's own `${...}` interpolation, by contrast, is NOT the blocker: every `${...}` in this file
    sits inside a scalar value (e.g. `Description: "${bot_description}"` at `:68`; `EndTimeoutMs:
    ${dtmf_end_timeout_ms}` at `:299` and elsewhere) and parses as an ordinary -- if semantically
    unresolved -- string under plain `yaml.safe_load`, confirmed the same way, in isolation. No `Name:`
    field under `Intents:`/`Slots:` anywhere in this file contains a `${...}` interpolation (checked
    directly against the live file, not assumed); Jinja/Terraform templating does not, today, reach a
    name this parser reads. `_slot_names`/`legal_slots_by_intent` below still raise loudly rather than
    silently return a bogus `"${...}"`-shaped name if that ever changes, because every extracted `Name:`
    is validated as a non-empty `str` on its own terms, not merely present.

    The fix mirrors `scripts/check_flows.py`'s own precedent (`substitute_template_placeholders`,
    `check_flows.py:84-91`): neutralize the one thing that blocks the real parser for this file's
    format, then parse for real, rather than hand-rolling a line-scanner that would have to
    re-implement YAML's own nesting rules. `check_flows.py` neutralizes Terraform's `${...}` so JSON
    parses; this module neutralizes CloudFormation's short-form tags so YAML parses -- same technique,
    a different blocker, because this file's blocker is different from that one's.

WHAT COUNTS AS MALFORMED, AND WHY AN EMPTY RESULT IS NOT ONE OF THE OPTIONS
    An intent with no `Slots:` key at all (`InjuryEscalation`, `FallbackIntent`) is a legitimate,
    zero-slot intent, and is simply absent from the returned mapping. An intent WITH a `Slots:` key that
    is missing, not a list, empty, or contains an entry with no valid `Name:` is a broken source of
    truth, not a zero-slot intent -- `legal_slots_by_intent` raises `SlotLegalityParseError` for it
    rather than omitting it or mapping it to an empty set. Returning `{}` (or omitting the intent
    silently) would make every future legality check against that intent vacuously pass -- the exact
    `D126` shape (`PROJECT_STATE.md`) this project has already filed once: a check that exists, finds
    nothing, and reads as clean.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import yaml


class SlotLegalityParseError(Exception):
    """The tftpl's `Intents:`/`Slots:` structure could not be read cleanly. Raised, never swallowed into
    an empty result -- see the module docstring's "malformed" section for why."""


class _CfnSafeLoader(yaml.SafeLoader):
    """`yaml.SafeLoader` plus CloudFormation's short-form intrinsic-function tags (`!Ref`, `!GetAtt`,
    and any other `!Xxx` this template gains later), resolved to an inert placeholder string rather than
    evaluated. Safe because this module only ever reads `Name:` fields under `Intents:`/`Slots:` -- it
    never inspects a `!Ref`/`!GetAtt` value, so what the placeholder contains is irrelevant, only that
    parsing does not stop at it."""


def _construct_cfn_short_form_tag(
    _loader: yaml.SafeLoader, tag_suffix: str, _node: yaml.Node
) -> str:
    return f"<{tag_suffix} unresolved>"


# types-PyYAML's own stub gap, not a defect in this code: yaml-stubs/constructor.pyi:39 declares
# `add_multi_constructor` with no parameter or return annotations at all -- same "third-party stub
# friction" category the Makefile's own TYPED comment already names for langgraph's stubs.
_CfnSafeLoader.add_multi_constructor(  # type: ignore[no-untyped-call]
    "!", _construct_cfn_short_form_tag
)


def _slot_names(intent_name: str, slots: Any) -> frozenset[str]:
    if not isinstance(slots, list) or not slots:
        raise SlotLegalityParseError(
            f"{intent_name!r} declares a Slots: block that is not a non-empty list (got {slots!r})"
        )
    names: set[str] = set()
    for entry in slots:
        name = entry.get("Name") if isinstance(entry, dict) else None
        if not isinstance(name, str) or not name:
            raise SlotLegalityParseError(
                f"{intent_name!r} has a Slots: entry with no valid Name: field (got {entry!r})"
            )
        names.add(name)
    return frozenset(names)


def legal_slots_by_intent(text: str) -> dict[str, frozenset[str]]:
    """`{intent name: frozenset of that intent's declared Lex slot names}`, for every intent in `text`
    that declares a `Slots:` block at all. See the module docstring for what counts as malformed and why
    a malformed block raises instead of contributing an empty set.
    """
    try:
        document = yaml.load(text, Loader=_CfnSafeLoader)
    except yaml.YAMLError as exc:
        raise SlotLegalityParseError(f"tftpl did not parse as YAML: {exc}") from exc

    try:
        locales = document["Resources"]["FnolBot"]["Properties"]["BotLocales"]
        intents = locales[0]["Intents"]
    except (KeyError, IndexError, TypeError) as exc:
        raise SlotLegalityParseError(
            "could not walk Resources.FnolBot.Properties.BotLocales[0].Intents"
        ) from exc

    if not isinstance(intents, list) or not intents:
        raise SlotLegalityParseError("Intents: is missing, empty, or not a list")

    mapping: dict[str, frozenset[str]] = {}
    for intent in intents:
        name = intent.get("Name") if isinstance(intent, dict) else None
        if not isinstance(name, str) or not name:
            raise SlotLegalityParseError(
                f"an intent entry has no valid Name: field (got {intent!r})"
            )
        if "Slots" not in intent:
            continue  # Legitimate zero-slot intent (InjuryEscalation, FallbackIntent) -- not malformed.
        mapping[name] = _slot_names(name, intent["Slots"])

    return mapping


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Extract and sanity-check the {intent: {slot names}} map bot.yaml.tftpl declares."
    )
    parser.add_argument(
        "--path",
        default="infra/terraform/stacks/main/bot.yaml.tftpl",
        help="Path to the CloudFormation bot template.",
    )
    parser.add_argument(
        "--require-at-least",
        type=int,
        default=1,
        help="Fail if fewer than this many slot-bearing intents are found -- finding nothing must never "
        "read as passing (same rule scripts/check_flows.py applies to flow discovery).",
    )
    args = parser.parse_args(argv)

    text = Path(args.path).read_text()
    try:
        mapping = legal_slots_by_intent(text)
    except SlotLegalityParseError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1

    if len(mapping) < args.require_at_least:
        print(
            f"FAIL: found {len(mapping)} slot-bearing intent(s) in {args.path}, "
            f"need at least {args.require_at_least}",
            file=sys.stderr,
        )
        return 1

    for name in sorted(mapping):
        print(f"{name}: {','.join(sorted(mapping[name]))}")
    print(f"OK: {len(mapping)} slot-bearing intent(s) extracted from {args.path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

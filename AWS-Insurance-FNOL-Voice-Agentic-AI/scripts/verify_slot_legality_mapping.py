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

# LINT-TIME ONLY -- never reaches the Lambda package. `infra/terraform/stacks/main/lambda.tf:44-54`
# packages only `source_dir = ".../src"`; this script lives in `scripts/`, entirely outside that root,
# and is never zipped up or invoked at runtime. Importing `fnol_voice_agent.api.lex_codehook` here is
# therefore safe from the circularity/runtime-availability concern rows 1/2's own module docstring
# raised (`_LEGAL_SLOTS_BY_INTENT` cannot import this module or its tftpl parse at runtime; the reverse
# -- this script importing that module, at lint time only -- has no such constraint) and is exactly
# what criterion 3's equality assert needs: the actual, currently-shipping constant, not a second
# hand-transcription of it.
from fnol_voice_agent.api.lex_codehook import _LEGAL_SLOTS_BY_INTENT


class SlotLegalityParseError(Exception):
    """The tftpl's `Intents:`/`Slots:` structure could not be read cleanly. Raised, never swallowed into
    an empty result -- see the module docstring's "malformed" section for why."""


class SlotLegalityDriftError(Exception):
    """`_LEGAL_SLOTS_BY_INTENT` (`src/fnol_voice_agent/api/lex_codehook.py`) has drifted from what
    `bot.yaml.tftpl` actually declares. Equality, not subset -- a subset assert over a partial constant
    would pass vacuously, the same `D126` shape (a check that exists, finds nothing, and reads as clean)
    `legal_slots_by_intent`'s own raise-on-malformed already guards against one level up: a constant
    missing an intent, or missing a legal slot name within an intent it does have, would make
    `_elicit_slot`'s row-1 filter drop, or row-2 raise on, a real, Lex-legal slot -- exactly the defect
    this equality check exists to catch."""


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


# `D200`/`OI118`. Names, not just membership -- each graph-internal slot survives only for the exact
# intent it's listed under, never blanket-exempted across all five. `CheckClaimStatus`'s
# `claim_or_policy_number` (`check_claim_status.py:19`) is a disambiguation slot the graph itself
# elicits, never declared in `bot.yaml.tftpl` and never a candidate to BE declared there -- Lex has no
# slot to fill for it, it exists only as the `slot_name` `_elicit_slot` is asked to route. Subtracted
# from `_LEGAL_SLOTS_BY_INTENT`'s side before the equality compare below, not folded into a weaker
# subset assert over the whole mapping -- an unlisted extra anywhere else must still fail loudly, the
# same `D126` shape this row's equality check exists to catch one level up.
_GRAPH_INTERNAL_SLOTS: dict[str, frozenset[str]] = {
    "CheckClaimStatus": frozenset({"claim_or_policy_number"}),
}


def assert_matches_src_constant(
    tftpl_mapping: dict[str, frozenset[str]], src_constant: dict[str, frozenset[str]]
) -> None:
    """Raise `SlotLegalityDriftError`, naming exactly what differs, unless `tftpl_mapping` (the parsed
    ground truth, `legal_slots_by_intent`'s own output) and `src_constant` (`_LEGAL_SLOTS_BY_INTENT`),
    AFTER subtracting `_GRAPH_INTERNAL_SLOTS` from `src_constant`'s side, are EQUAL -- same intent keys,
    same slot-name set per key. Still equality, not subset, over what's left after that one named
    allowlist is removed: see `SlotLegalityDriftError`'s own docstring for why a bare subset assert
    over the whole mapping would pass vacuously instead.
    """
    effective_src_constant = {
        intent: slots - _GRAPH_INTERNAL_SLOTS.get(intent, frozenset())
        for intent, slots in src_constant.items()
    }
    if tftpl_mapping == effective_src_constant:
        return

    src_constant = effective_src_constant
    lines: list[str] = []
    tftpl_only_intents = sorted(set(tftpl_mapping) - set(src_constant))
    constant_only_intents = sorted(set(src_constant) - set(tftpl_mapping))
    if tftpl_only_intents:
        lines.append(
            f"intent(s) in bot.yaml.tftpl but missing from _LEGAL_SLOTS_BY_INTENT: {tftpl_only_intents}"
        )
    if constant_only_intents:
        lines.append(
            "intent(s) in _LEGAL_SLOTS_BY_INTENT but not declared in bot.yaml.tftpl: "
            f"{constant_only_intents}"
        )
    for intent in sorted(set(tftpl_mapping) & set(src_constant)):
        tftpl_slots = tftpl_mapping[intent]
        constant_slots = src_constant[intent]
        if tftpl_slots == constant_slots:
            continue
        missing = sorted(tftpl_slots - constant_slots)
        extra = sorted(constant_slots - tftpl_slots)
        detail = f"{intent!r}:"
        if missing:
            detail += f" missing from _LEGAL_SLOTS_BY_INTENT={missing}"
        if extra:
            detail += f" extra in _LEGAL_SLOTS_BY_INTENT (not declared in bot.yaml.tftpl)={extra}"
        lines.append(detail)

    raise SlotLegalityDriftError(
        "_LEGAL_SLOTS_BY_INTENT has drifted from bot.yaml.tftpl:\n" + "\n".join(lines)
    )


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

    # `D162`/`OI80` criterion 3's equality assert. `_LEGAL_SLOTS_BY_INTENT` is what `_elicit_slot`
    # actually runs against (rows 1/2) -- this is what keeps it from silently drifting from what
    # bot.yaml.tftpl declares now that both exist.
    try:
        assert_matches_src_constant(mapping, _LEGAL_SLOTS_BY_INTENT)
    except SlotLegalityDriftError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    print(
        "OK: _LEGAL_SLOTS_BY_INTENT (src/fnol_voice_agent/api/lex_codehook.py) matches bot.yaml.tftpl"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

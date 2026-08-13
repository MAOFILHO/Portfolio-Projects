"""Negative controls for the contact-flow CI check.

Phase 8 Stage 3. Same discipline as `test_lexpoc_gate.py`: **the shipped flow is the fixture, and every
test mutates it into one specific violation.** A guard only ever seen to pass is not known to work, and a
guard whose failure cases are written from imagination tends to catch the failures its author imagined.

Two of these are about the checker's own reach rather than about any flow:

  * `test_a_flow_with_no_extension_is_still_found` — `CLAUDE.md` requires globbing by content because
    some upstream exports have no extension. An extension glob would skip them silently, and a check
    that examines zero files passes.
  * `test_finding_no_flows_at_all_is_a_failure` — the same failure one level up. This is the tag-filter
    lesson from Stage 0: a filter that matches nothing reports $0 forever and looks like success.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest

from scripts.check_flows import (
    check_flow,
    check_recording_is_off,
    check_tagged_before_every_ending,
    discover_flows,
    main,
    parse_flow,
    substitute_template_placeholders,
)

SHIPPED_FLOW = (
    Path(__file__).resolve().parents[2]
    / "infra/terraform/stacks/main/flows/fnol-inbound.json.tftpl"
)


@pytest.fixture
def flow() -> dict[str, Any]:
    """The real deployed flow, parsed. Not a hand-written miniature of one."""
    document = parse_flow(SHIPPED_FLOW.read_text(encoding="utf-8"))
    assert document is not None, "the shipped flow no longer parses as a contact flow"
    return copy.deepcopy(document)


@pytest.fixture
def flow_text() -> str:
    return SHIPPED_FLOW.read_text(encoding="utf-8")


def _action(flow: dict[str, Any], identifier: str) -> dict[str, Any]:
    for action in flow["Actions"]:
        if action["Identifier"] == identifier:
            return action
    raise AssertionError(f"{identifier} is no longer in the shipped flow")


def _write(tmp_path: Path, name: str, document: dict[str, Any]) -> Path:
    path = tmp_path / name
    path.write_text(json.dumps(document, indent=2), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------------------------------
# The shipped flow passes. Stated once, so every failure below is a delta from a known-good baseline.
# ---------------------------------------------------------------------------------------------------


def test_the_shipped_flow_is_clean(flow: dict[str, Any], flow_text: str) -> None:
    assert check_flow(SHIPPED_FLOW, flow, flow_text) == []


# ---------------------------------------------------------------------------------------------------
# Constraint 18 — all three recording switches
# ---------------------------------------------------------------------------------------------------


def test_recording_a_participant_fails(flow: dict[str, Any]) -> None:
    behaviour = _action(flow, "RecordingOff")["Parameters"]["RecordingBehavior"]
    behaviour["RecordedParticipants"] = ["Agent", "Customer"]

    violations = check_recording_is_off(flow)

    assert any("RecordedParticipants" in v for v in violations)


def test_screen_recording_fails(flow: dict[str, Any]) -> None:
    """Not covered by an empty `RecordedParticipants`. A separate list, a separate switch."""
    behaviour = _action(flow, "RecordingOff")["Parameters"]["RecordingBehavior"]
    behaviour["ScreenRecordedParticipants"] = ["Agent"]

    assert any("ScreenRecordedParticipants" in v for v in check_recording_is_off(flow))


def test_ivr_recording_fails_even_with_an_empty_participant_list(flow: dict[str, Any]) -> None:
    """The gap in constraint 18's check as `CLAUDE.md` words it.

    `RecordedParticipants: []` with `IVRRecordingBehavior: "Enabled"` records the caller's entire
    self-service conversation — which is the only leg this system has, because there are no agents —
    while satisfying a check written only against the participant list.
    """
    behaviour = _action(flow, "RecordingOff")["Parameters"]["RecordingBehavior"]
    behaviour["RecordedParticipants"] = []
    behaviour["IVRRecordingBehavior"] = "Enabled"

    violations = check_recording_is_off(flow)

    assert any("IVRRecordingBehavior" in v for v in violations)


def test_a_recording_action_with_no_behaviour_object_fails(flow: dict[str, Any]) -> None:
    """Absent is not off. An unspecified recording state is a state nobody chose."""
    _action(flow, "RecordingOff")["Parameters"] = {}

    assert check_recording_is_off(flow) != []


# ---------------------------------------------------------------------------------------------------
# Banned analytics
# ---------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("banned", ["AnalyticsBehavior", "ContactLens", "RealTimeContactAnalysis"])
def test_each_banned_analytics_name_fails(
    flow: dict[str, Any], flow_text: str, banned: str
) -> None:
    assert check_flow(SHIPPED_FLOW, flow, flow_text + f"\n// {banned}\n") != []


# ---------------------------------------------------------------------------------------------------
# The contact tag schema
# ---------------------------------------------------------------------------------------------------


def test_an_extra_contact_tag_fails(flow: dict[str, Any], flow_text: str) -> None:
    """`Intent` is the specific tag `CONTACT-TAG-SCHEMA.md` argues hardest against, so it is the one
    tested: one of the six intents is `InjuryEscalation`, and a contact tagged with it, joined to a
    contact record carrying the caller's number, is a health-adjacent inference in a billing system.
    """
    _action(flow, "TagTheContact")["Parameters"]["Tags"]["Intent"] = "InjuryEscalation"

    violations = check_flow(SHIPPED_FLOW, flow, flow_text)

    assert any("Intent" in v for v in violations)


def test_a_plausible_looking_extra_tag_also_fails(flow: dict[str, Any], flow_text: str) -> None:
    """The schema left three slots empty on purpose. `Team` is harmless and still not decided."""
    _action(flow, "TagTheContact")["Parameters"]["Tags"]["Team"] = "claims"

    assert check_flow(SHIPPED_FLOW, flow, flow_text) != []


def test_the_three_allowed_tags_pass(flow: dict[str, Any], flow_text: str) -> None:
    """The complement of the two tests above: the check is not simply rejecting every TagContact."""
    tags = _action(flow, "TagTheContact")["Parameters"]["Tags"]

    assert set(tags) == {"Project", "Env", "FlowVersion"}
    assert check_flow(SHIPPED_FLOW, flow, flow_text) == []


# ---------------------------------------------------------------------------------------------------
# Reachability — a tag on only some paths is the failure Stage 0's audit was about
# ---------------------------------------------------------------------------------------------------


def test_a_disconnect_reachable_before_the_tag_fails(flow: dict[str, Any]) -> None:
    """The realistic version of this mistake: an error branch added to the FIRST action, which runs
    before the tag block, wired straight to a hangup."""
    _action(flow, "RecordingOff")["Transitions"]["Errors"] = [
        {"ErrorType": "NoMatchingError", "NextAction": "Hangup"}
    ]

    violations = check_tagged_before_every_ending(flow)

    assert any("Hangup" in v for v in violations)


def test_removing_the_tag_block_entirely_fails(flow: dict[str, Any]) -> None:
    flow["Actions"] = [a for a in flow["Actions"] if a["Type"] != "TagContact"]
    _action(flow, "RecordingOff")["Transitions"]["NextAction"] = "Greeting"

    assert check_tagged_before_every_ending(flow) != []


def test_moving_the_tag_after_the_greeting_still_passes(flow: dict[str, Any]) -> None:
    """A true negative, and the reason this check is reachability rather than "is it action number two".

    Order within the untagged prefix does not matter; what matters is that nothing ENDS untagged. A check
    that failed here would be enforcing a style, and would be argued away the first time it was wrong.

    THE FIRST DRAFT OF THIS TEST FAILED, AND THE CHECKER WAS RIGHT. Moving the tag below `Greeting` left
    `Greeting`'s own error branch pointing at `Agent`, one step past the tag — so a caller whose greeting
    failed to play would reach a hangup untagged. That is precisely the partial-coverage failure
    `CONTACT-TAG-SCHEMA.md` consequence 1 exists for, it was introduced here by someone deliberately
    writing a *benign* reordering, and eyeballing the reordered flow did not reveal it. Recorded in the
    test rather than quietly fixed, because it is the strongest evidence available that the check earns
    its keep.
    """
    _action(flow, "RecordingOff")["Transitions"]["NextAction"] = "Greeting"
    _action(flow, "Greeting")["Transitions"]["NextAction"] = "TagTheContact"
    _action(flow, "Greeting")["Transitions"]["Errors"] = [
        {"ErrorType": "NoMatchingError", "NextAction": "TagTheContact"}
    ]
    _action(flow, "TagTheContact")["Transitions"]["NextAction"] = "Agent"

    assert check_tagged_before_every_ending(flow) == []


def test_a_transition_to_a_nonexistent_action_fails(flow: dict[str, Any]) -> None:
    _action(flow, "Goodbye")["Transitions"]["NextAction"] = "NoSuchAction"

    assert check_tagged_before_every_ending(flow) != []


def test_a_start_action_naming_nothing_fails(flow: dict[str, Any]) -> None:
    flow["StartAction"] = "NotARealIdentifier"

    assert check_tagged_before_every_ending(flow) != []


# ---------------------------------------------------------------------------------------------------
# Discovery — the half of this check that fails by finding nothing
# ---------------------------------------------------------------------------------------------------


def test_a_flow_with_no_extension_is_still_found(tmp_path: Path, flow: dict[str, Any]) -> None:
    """`CLAUDE.md`: glob by content, not by `.json`. Some upstream exports have no extension."""
    (tmp_path / "inbound_flow_export").write_text(json.dumps(flow), encoding="utf-8")

    found = discover_flows(tmp_path)

    assert [p.name for p, _, _ in found] == ["inbound_flow_export"]


def test_a_flow_with_a_misleading_extension_is_still_found(
    tmp_path: Path, flow: dict[str, Any]
) -> None:
    _write(tmp_path, "flow.txt", flow)

    assert len(discover_flows(tmp_path)) == 1


def test_a_json_file_that_is_not_a_flow_is_ignored(tmp_path: Path) -> None:
    """`Actions`/`modules` is the identification rule. Without it, every JSON file in the repo becomes a
    flow that fails the "no TagContact" check, and the check gets deleted for crying wolf."""
    (tmp_path / "package.json").write_text(json.dumps({"name": "x"}), encoding="utf-8")

    assert discover_flows(tmp_path) == []


def test_a_module_style_flow_is_recognised(tmp_path: Path) -> None:
    (tmp_path / "legacy_export").write_text(json.dumps({"modules": []}), encoding="utf-8")

    assert len(discover_flows(tmp_path)) == 1


def test_finding_no_flows_at_all_is_a_failure(tmp_path: Path) -> None:
    """Stage 0's lesson, applied to this checker: a filter that matches nothing reports success."""
    assert main(["--root", str(tmp_path)]) == 1


def test_the_checker_exits_non_zero_on_a_bad_flow(tmp_path: Path, flow: dict[str, Any]) -> None:
    """End to end through `main`, because every test above calls a function directly and a checker that
    computes the right violations and exits 0 is a checker CI ignores."""
    _action(flow, "RecordingOff")["Parameters"]["RecordingBehavior"]["RecordedParticipants"] = [
        "Customer"
    ]
    _write(tmp_path, "bad_flow", flow)

    assert main(["--root", str(tmp_path)]) == 1


def test_the_checker_exits_zero_on_the_shipped_tree() -> None:
    assert main([]) == 0


# ---------------------------------------------------------------------------------------------------
# Template handling
# ---------------------------------------------------------------------------------------------------


def test_placeholders_are_substituted_rather_than_the_file_being_skipped() -> None:
    """The shipped flow is a `templatefile()` source. If placeholder substitution regressed, the file
    would stop parsing and `discover_flows` would silently stop returning it — which is the same
    zero-files failure as an extension glob, arriving by a different route."""
    raw = SHIPPED_FLOW.read_text(encoding="utf-8")

    assert "${" in raw
    assert "${" not in substitute_template_placeholders(raw)
    assert parse_flow(raw) is not None

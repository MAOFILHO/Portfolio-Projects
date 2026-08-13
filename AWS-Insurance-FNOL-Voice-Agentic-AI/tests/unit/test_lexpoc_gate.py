"""Negative controls for `ADR-007`'s POC gate.

The gate passed. That is not evidence that it works, and this project has now been caught by that three
times (`RESULTS.md` §3.5): `verify-backend` matched a comment and looked green, the fingerprint hashed
three of six files and looked green, criterion 3's first demonstration failed on the wrong error and
looked like a guard firing.

So every claim `scripts/lexpoc_gate.py` makes is exercised here against a mutated snapshot in which that
claim is false. The mutations are the actual failure modes, written out:

  * #42147's signature -- the deployed definition does not move while the apply reports success;
  * a stale build -- the definition moves and the runtime keeps serving the old prompt;
  * a gate run twice against the same template, which would pass while testing nothing;
  * an update that moved a field no template touched.

The fixtures are the real recorded snapshots from the live applies, not hand-written ones, so a test
here fails if the evidence files are ever replaced with something that does not support the finding.

Pure functions only. No AWS calls, no credentials.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest

from scripts.lexpoc_gate import (
    EXPECTED_SLOT_ORDER,
    check_change,
    check_removal,
    check_snapshot,
)

EVIDENCE = Path(__file__).resolve().parents[2] / "docs" / "evidence" / "phase8"


def _load(name: str) -> dict[str, Any]:
    return json.loads((EVIDENCE / name).read_text())


@pytest.fixture
def before() -> dict[str, Any]:
    return _load("lexpoc-apply-1.json")


@pytest.fixture
def after() -> dict[str, Any]:
    return _load("lexpoc-apply-2.json")


@pytest.fixture
def removed() -> dict[str, Any]:
    return _load("lexpoc-apply-3.json")


# --------------------------------------------------------------------------------------------------
# The recorded result
# --------------------------------------------------------------------------------------------------


def test_recorded_applies_pass_the_gate(before: dict[str, Any], after: dict[str, Any]) -> None:
    """The evidence on disk is what ADR-007's gate was discharged on."""
    assert check_change(before, after) == []
    assert check_snapshot(before) == []
    assert check_snapshot(after) == []


def test_the_two_snapshots_really_are_of_different_templates(
    before: dict[str, Any], after: dict[str, Any]
) -> None:
    assert (
        before["declared"]["template_sha256"] != after["declared"]["template_sha256"]
    ), "the recorded pair must span an actual template change or it proves nothing"


def test_eleven_slots_deployed_with_the_designed_priority_order(after: dict[str, Any]) -> None:
    """#39948's cycle, and the reason the nested shape was chosen over the native resources."""
    assert after["definition"]["slot_count"] == 11
    assert after["definition"]["slot_order"] == EXPECTED_SLOT_ORDER


# --------------------------------------------------------------------------------------------------
# Negative controls -- one per claim the gate makes
# --------------------------------------------------------------------------------------------------


def test_gate_fails_on_42147s_signature(before: dict[str, Any], after: dict[str, Any]) -> None:
    """The deployed definition did not move, but the apply reported success.

    This is the exact defect ADR-007 rejected the native provider over, transplanted into the nested
    path. If the gate cannot see it here, it could not have seen it there.
    """
    silent = copy.deepcopy(after)
    silent["definition"]["subject_initial_prompt"] = before["definition"]["subject_initial_prompt"]

    failures = check_change(before, silent)
    assert any("#42147" in f for f in failures)


def test_gate_fails_when_the_advanced_setting_alone_is_ignored(
    before: dict[str, Any], after: dict[str, Any]
) -> None:
    """A mechanism could get the prompt string right and the nested integer wrong -- #36845's family."""
    partial = copy.deepcopy(after)
    partial["definition"]["subject_retry1_dtmf_end_timeout_ms"] = before["definition"][
        "subject_retry1_dtmf_end_timeout_ms"
    ]

    failures = check_change(before, partial)
    assert any("retry1 dtmf endTimeoutMs unchanged" in f for f in failures)


def test_gate_fails_on_a_stale_build(before: dict[str, Any], after: dict[str, Any]) -> None:
    """Definition current, runtime serving the old wording. The artifact-versus-outcome split."""
    stale = copy.deepcopy(after)
    stale["runtime"]["spoken_subject_prompt"] = before["runtime"]["spoken_subject_prompt"]

    failures = check_change(before, stale)
    assert any("RUNTIME prompt unchanged" in f for f in failures)


def test_gate_fails_when_compared_against_itself(after: dict[str, Any]) -> None:
    """Two snapshots of the same template. Every field agrees, and nothing was tested.

    Without this check the gate's happiest possible output is also its emptiest.
    """
    failures = check_change(after, copy.deepcopy(after))
    assert any("share a template hash" in f for f in failures)


def test_gate_fails_when_the_control_field_moves(
    before: dict[str, Any], after: dict[str, Any]
) -> None:
    """A field no template templated has changed -- the update did more than it declared."""
    overreach = copy.deepcopy(after)
    overreach["definition"]["control_retry1_dtmf_end_timeout_ms"] = 1234

    failures = check_change(before, overreach)
    assert any("CONTROL moved" in f for f in failures)


def test_snapshot_check_fails_when_deployment_disagrees_with_terraform(
    after: dict[str, Any],
) -> None:
    drifted = copy.deepcopy(after)
    drifted["definition"]["subject_initial_prompt"] = "something nobody declared"

    failures = check_snapshot(drifted)
    assert any("DEFINITION prompt" in f for f in failures)


def test_snapshot_check_fails_when_the_locale_is_not_built(after: dict[str, Any]) -> None:
    """`ReadyExpressTesting` is a real state this bot passed through on both applies."""
    building = copy.deepcopy(after)
    building["definition"]["locale_status"] = "ReadyExpressTesting"

    failures = check_snapshot(building)
    assert any("not Built" in f for f in failures)


def test_snapshot_check_fails_on_a_truncated_slot_list(after: dict[str, Any]) -> None:
    """`ListSlots` pages at 10 by default and this intent has 11.

    An unpaginated read returns a plausible-looking set that is missing `other_party_involved`. The
    count assertion is what turns that from a silent omission into a failure.
    """
    truncated = copy.deepcopy(after)
    truncated["definition"]["slot_count"] = 10
    truncated["definition"]["slot_order"] = EXPECTED_SLOT_ORDER[:10]

    failures = check_snapshot(truncated)
    assert any("10 slots deployed" in f for f in failures)


def test_recorded_removal_actually_left_the_bot(
    after: dict[str, Any], removed: dict[str, Any]
) -> None:
    """The third apply's question: does a deletion propagate, or does the update merge?"""
    assert check_removal(after, removed) == []
    assert len(after["runtime"]["subject_prompt_messages"]) == 2
    assert len(removed["runtime"]["subject_prompt_messages"]) == 1


def test_removal_check_fails_when_the_deleted_message_is_still_served(
    after: dict[str, Any], removed: dict[str, Any]
) -> None:
    """Negative control: a merge-not-replace update, which is the failure this check exists for."""
    merged = copy.deepcopy(removed)
    merged["runtime"]["subject_prompt_messages"] = after["runtime"]["subject_prompt_messages"]

    failures = check_removal(after, merged)
    assert any("did not disappear" in f for f in failures)


def test_removal_check_fails_when_nothing_was_removed(after: dict[str, Any]) -> None:
    """Comparing a snapshot with itself must not read as a successful deletion."""
    failures = check_removal(after, copy.deepcopy(after))
    assert any("tested nothing" in f for f in failures)


def test_snapshot_check_fails_when_priority_order_is_wrong(after: dict[str, Any]) -> None:
    """Safety is asked first. An order that quietly demotes it is the one reordering that matters."""
    reordered = copy.deepcopy(after)
    order = list(EXPECTED_SLOT_ORDER)
    order[0], order[1] = order[1], order[0]
    reordered["definition"]["slot_order"] = order

    failures = check_snapshot(reordered)
    assert any("slot priority order" in f for f in failures)

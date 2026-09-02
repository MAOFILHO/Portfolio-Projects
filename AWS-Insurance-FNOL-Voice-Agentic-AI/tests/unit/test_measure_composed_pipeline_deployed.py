"""`D81` items 1, 4, 5 — `scripts/measure_composed_pipeline_deployed.py`'s classification and scoring
logic, unit-tested against constructed `RecognizeText`-shaped responses. No real AWS call anywhere in
this file: `ADR-013` reserves that for the script itself when actually run against the live alias, which
this suite deliberately never does -- every `recognize_text` call below is a fake object's canned return
value, not `mock_aws()` (there is no AWS service surface here to mock; `lexv2-runtime` isn't in moto's
supported set) and not a real `boto3` client.
"""

from __future__ import annotations

from typing import Any

import pytest

from evals.holdout import HoldoutKind, InjuryPhrasing
from fnol_voice_agent.models.enums import KabcoCode
from scripts.measure_composed_pipeline_deployed import (
    RunInvalidError,
    _classify_invocation,
    measure_negatives,
    measure_positives,
    provenance_breakdown,
    worst_case_detection,
)


def _phrasing(text: str, *, should_escalate: bool) -> InjuryPhrasing:
    return InjuryPhrasing(
        text=text,
        kabco=KabcoCode.NO_INJURY,
        should_escalate=should_escalate,
        kind=HoldoutKind.INDEPENDENT,
    )


def _response(
    *,
    intent_name: str = "FileAutoClaim",
    intent_state: str = "InProgress",
    escalate: str | None = None,
    escalation_reason: str | None = None,
) -> dict[str, Any]:
    session_attributes: dict[str, str] = {}
    if escalate is not None:
        session_attributes["escalate"] = escalate
    if escalation_reason is not None:
        session_attributes["escalation_reason"] = escalation_reason
    return {
        "sessionState": {
            "dialogAction": {"type": "Close"},
            "intent": {"name": intent_name, "state": intent_state},
            "sessionAttributes": session_attributes,
        },
        "messages": [],
    }


class _FakeRuntime:
    """`recognize_text(**_)` returns responses from a fixed queue, one per call, in order -- the fake
    object `measure_positives`/`measure_negatives` are written against, standing in for
    `boto3.client("lexv2-runtime")`."""

    def __init__(self, responses: list[dict[str, Any]]) -> None:
        self._responses = list(responses)

    def recognize_text(self, **_: Any) -> dict[str, Any]:
        return self._responses.pop(0)


# ---------------------------------------------------------------------------------------------------
# `D81` item 1 -- the Lex-native-fallback shape is `invalid`, not a silent `not-escalated`
# ---------------------------------------------------------------------------------------------------


def test_lex_native_fallback_shape_is_invalid() -> None:
    """The exact shape `RESULTS.md` §11.4 recorded from the real 79/79-error run."""
    status, reason = _classify_invocation(
        _response(intent_name="FallbackIntent", intent_state="Failed")
    )
    assert status == "invalid"
    assert reason is None


def test_an_ordinary_fallback_intent_that_is_not_failed_is_not_treated_as_invalid() -> None:
    """Only the (name, state) PAIR is the crash signature -- a `FallbackIntent` on its own can be a
    legitimate no-match turn (unrelated to this project's cold-start crash), and must not be conflated
    with it."""
    status, _ = _classify_invocation(
        _response(intent_name="FallbackIntent", intent_state="InProgress")
    )
    assert status == "not-escalated"


# ---------------------------------------------------------------------------------------------------
# `D81` item 4 -- provenance read from `sessionAttributes.escalation_reason`
# ---------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw_reason,expected",
    [
        ("detection-pregraph", "detection-pregraph"),
        ("detection-graph", "detection-graph"),
        ("fail-closed", "fail-closed"),
        (None, "other-default"),
        (
            "detection",
            "other-default",
        ),  # the old, pre-split value -- must not silently pass as either
        ("some-future-value", "other-default"),
    ],
)
def test_escalation_reason_is_read_and_unknown_values_fall_back_to_other_default(
    raw_reason: str | None, expected: str
) -> None:
    status, reason = _classify_invocation(_response(escalate="true", escalation_reason=raw_reason))
    assert status == "escalated"
    assert reason == expected


def test_no_escalate_attribute_is_not_escalated() -> None:
    status, reason = _classify_invocation(_response())
    assert status == "not-escalated"
    assert reason is None


# ---------------------------------------------------------------------------------------------------
# `D81` item 4 -- scoring requires `detection` provenance on every sample, not just `escalate=true`
# ---------------------------------------------------------------------------------------------------


def test_worst_case_detection_passes_when_every_sample_is_pregraph_detection() -> None:
    all_detection = [
        {"status": "escalated", "escalation_reason": "detection-pregraph"},
        {"status": "escalated", "escalation_reason": "detection-pregraph"},
    ]
    assert worst_case_detection(all_detection) is True


def test_worst_case_detection_passes_when_every_sample_is_graph_detection() -> None:
    all_detection = [
        {"status": "escalated", "escalation_reason": "detection-graph"},
        {"status": "escalated", "escalation_reason": "detection-graph"},
    ]
    assert worst_case_detection(all_detection) is True


def test_worst_case_detection_passes_on_a_mix_of_pregraph_and_graph_detection() -> None:
    """Both provenance values are genuine detections -- the split shows WHICH path fired, it does not
    rank one above the other. A sample-by-sample mix (e.g. the graph caught it after L1 missed on a
    different sample) must still pass."""
    mixed_but_both_detections = [
        {"status": "escalated", "escalation_reason": "detection-pregraph"},
        {"status": "escalated", "escalation_reason": "detection-graph"},
    ]
    assert worst_case_detection(mixed_but_both_detections) is True


def test_worst_case_detection_fails_on_a_single_fail_closed_sample() -> None:
    """The exact case `D81`'s expanded entry names: a broken detector plus an always-firing fail-closed
    path must not score as a passing measurement."""
    mixed = [
        {"status": "escalated", "escalation_reason": "detection-pregraph"},
        {"status": "escalated", "escalation_reason": "fail-closed"},
    ]
    assert worst_case_detection(mixed) is False


def test_worst_case_detection_fails_on_a_not_escalated_sample() -> None:
    mixed: list[dict[str, Any]] = [
        {"status": "escalated", "escalation_reason": "detection-pregraph"},
        {"status": "not-escalated", "escalation_reason": None},
    ]
    assert worst_case_detection(mixed) is False


# ---------------------------------------------------------------------------------------------------
# `D81` item 1 -- any `invalid` sample aborts the run immediately, on positives or negatives
# ---------------------------------------------------------------------------------------------------


def test_measure_positives_aborts_the_run_on_an_invalid_sample() -> None:
    """Regression test for the exact incident: today's still-broken deployed function crashes at
    cold-start import on every call, which reads as this shape on every one of the k samples. A passing
    `escalated`/`not-escalated` bucket must never be computed from a run containing it."""
    runtime = _FakeRuntime([_response(intent_name="FallbackIntent", intent_state="Failed")] * 3)
    with pytest.raises(RunInvalidError, match="invalid invocation"):
        measure_positives(
            runtime,
            [_phrasing("my passenger isn't moving", should_escalate=True)],
            bot_id="bot",
            bot_alias_id="alias",
        )


def test_measure_negatives_aborts_the_run_on_an_invalid_sample() -> None:
    runtime = _FakeRuntime([_response(intent_name="FallbackIntent", intent_state="Failed")])
    with pytest.raises(RunInvalidError, match="invalid invocation"):
        measure_negatives(
            runtime,
            [_phrasing("my agent said the check is in the mail", should_escalate=False)],
            bot_id="bot",
            bot_alias_id="alias",
        )


# ---------------------------------------------------------------------------------------------------
# `D81` item 5 -- negative-control saturation is an instrument defect, not a scored false-escalation
# ---------------------------------------------------------------------------------------------------


def test_negative_saturation_raises_run_invalid_not_a_false_escalation_score() -> None:
    """A broken detector that escalates on every true negative must not silently produce a scored
    false-escalation rate -- it has to abort the run the same way an `invalid` sample does, per D81 item
    5's explicit 'this is an instrument defect, not a false-escalation defect.'"""
    negatives = [_phrasing(f"benign utterance {i}", should_escalate=False) for i in range(3)]
    runtime = _FakeRuntime([_response(escalate="true", escalation_reason="detection-pregraph")] * 3)
    with pytest.raises(RunInvalidError, match="saturation"):
        measure_negatives(runtime, negatives, bot_id="bot", bot_alias_id="alias")


def test_negative_partial_false_escalation_is_reported_not_fatal() -> None:
    negatives = [_phrasing(f"benign utterance {i}", should_escalate=False) for i in range(3)]
    runtime = _FakeRuntime(
        [
            _response(escalate="true", escalation_reason="detection-pregraph"),
            _response(),
            _response(),
        ]
    )
    items, total_calls = measure_negatives(runtime, negatives, bot_id="bot", bot_alias_id="alias")
    assert total_calls == 3
    assert sum(1 for i in items if i["falsely_escalated"]) == 1


# ---------------------------------------------------------------------------------------------------
# Provenance breakdown -- attached to the reported number, not left as per-item detail
# ---------------------------------------------------------------------------------------------------


def test_provenance_breakdown_rolls_up_positives_and_negatives() -> None:
    positive_items = [
        {"escalation_reasons": ["detection-pregraph", "detection-pregraph", "detection-graph"]},
        {"escalation_reasons": ["fail-closed", "detection-pregraph", "detection-graph"]},
    ]
    negative_items: list[dict[str, Any]] = [
        {"falsely_escalated": True, "escalation_reason": "other-default"},
        {"falsely_escalated": False, "escalation_reason": None},
    ]
    counts = provenance_breakdown(positive_items, negative_items)
    assert counts == {
        "detection-pregraph": 3,
        "detection-graph": 2,
        "fail-closed": 1,
        "other-default": 1,
    }

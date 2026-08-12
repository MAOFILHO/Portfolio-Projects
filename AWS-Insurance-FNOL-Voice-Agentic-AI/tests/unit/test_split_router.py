"""The unmerged router — `ADR-014` Stage 3.

Grouped by the invariant each test defends, because that is what these tests are for. The split's
metrics are the ablation ladder's business; this file's business is that the split cannot quietly
lose a property the merged call had for free.

Every test injects a fake caller. No real Bedrock call happens here (`ADR-013`).
"""

from __future__ import annotations

import threading
from collections.abc import Mapping
from typing import Any

import pytest
from pydantic import ValidationError

from fnol_voice_agent.agents.testing.fake_llm import (
    FakeBedrockConverseClient,
    converse_text_response,
    converse_tool_use_response,
)
from fnol_voice_agent.aws import split_router
from fnol_voice_agent.aws.bedrock_router import (
    _CLASSIFY_TURN_SYSTEM_PROMPT,
    BedrockRouterError,
)
from fnol_voice_agent.aws.split_router import (
    CLASSIFY_INTENT_TOOL_NAME,
    DETECT_INJURY_TOOL_NAME,
    VERBATIM_INJURY_INSTRUCTION,
    DetectorVetoedError,
    assert_detector_dominates,
    classify_intent,
    classify_turn_split,
    combine,
    detect_injury,
)
from fnol_voice_agent.config.settings import ROUTER_MODEL_ID
from fnol_voice_agent.models.enums import CoverageQuestionType, Intent
from fnol_voice_agent.models.routing import InjuryVerdict, IntentClassification


def _turn(text: str = "there's blood everywhere") -> list[dict[str, object]]:
    return [{"role": "user", "content": [{"text": text}]}]


def _detector(indicated: bool) -> dict[str, Any]:
    return converse_tool_use_response(DETECT_INJURY_TOOL_NAME, {"injury_indicated": indicated})


def _classifier(intent: str = "CoverageQuestion", confidence: float = 0.9) -> dict[str, Any]:
    return converse_tool_use_response(
        CLASSIFY_INTENT_TOOL_NAME,
        {"intent": intent, "intent_confidence": confidence},
    )


class ByToolCaller:
    """Dispatches on the forced tool name instead of on call order.

    `FakeBedrockConverseClient` returns queued responses FIFO, which is right for a sequence of
    calls and wrong for two concurrent ones: the split submits both legs to a thread pool, so
    whichever thread reaches `converse` first takes the head of the queue. A FIFO fake would make
    every test here a coin flip that usually lands the right way up -- the worst kind of test,
    since it passes in CI until it doesn't.

    Records `calls` under a lock so assertions over the recorded kwargs are not racing either.
    """

    def __init__(self, **by_tool: Mapping[str, Any]) -> None:
        self._by_tool = dict(by_tool)
        self.calls: list[dict[str, Any]] = []
        self._lock = threading.Lock()

    def converse(self, **kwargs: Any) -> dict[str, Any]:
        with self._lock:
            self.calls.append(kwargs)
        tool = kwargs["toolConfig"]["toolChoice"]["tool"]["name"]
        return dict(self._by_tool[tool])


def _split_caller(
    *, injury: bool = False, intent: str = "CoverageQuestion", confidence: float = 0.9
) -> ByToolCaller:
    return ByToolCaller(
        **{
            DETECT_INJURY_TOOL_NAME: _detector(injury),
            CLASSIFY_INTENT_TOOL_NAME: _classifier(intent, confidence),
        }
    )


# --- I3: the detector cannot be vetoed ------------------------------------------------------------


@pytest.mark.parametrize("injury", [True, False])
@pytest.mark.parametrize("classifier_intent", [Intent.INJURY_ESCALATION, Intent.COVERAGE_QUESTION])
def test_safety_flag_is_always_the_detector_verdict(
    injury: bool, classifier_intent: Intent
) -> None:
    """Merged, the safety verdict was structurally inseparable from routing -- an ugly property that
    made bypass impossible. Two calls make bypass expressible for the first time, so the property is
    now asserted rather than inherited."""
    combined = combine(
        InjuryVerdict(injury_indicated=injury),
        IntentClassification(intent=classifier_intent, intent_confidence=1.0),
    )
    assert combined is not None
    assert combined.safety_flag is injury


def test_a_fired_detector_forces_the_effective_intent() -> None:
    combined = combine(
        InjuryVerdict(injury_indicated=True),
        IntentClassification(intent=Intent.CHECK_CLAIM_STATUS, intent_confidence=1.0),
    )
    assert combined is not None
    assert combined.intent is Intent.INJURY_ESCALATION


def test_a_silent_detector_leaves_the_classifier_intent_alone() -> None:
    combined = combine(
        InjuryVerdict(injury_indicated=False),
        IntentClassification(
            intent=Intent.RENTAL_TOWING_ENTITLEMENT,
            intent_confidence=0.7,
            coverage_question_type=CoverageQuestionType.NOT_APPLICABLE,
        ),
    )
    assert combined is not None
    assert combined.intent is Intent.RENTAL_TOWING_ENTITLEMENT
    assert combined.safety_flag is False


def test_combine_takes_no_argument_that_could_override_the_verdict() -> None:
    """A keyword like `prefer_intent=` or `escalate=False` is how `I3` would be lost in practice --
    added for one plausible-sounding case, then reachable from everywhere. Checked against the
    signature so the absence is enforced, not just currently true."""
    import inspect

    params = list(inspect.signature(combine).parameters)
    assert params == ["verdict", "intent"]


def test_the_construction_time_dominance_check_passes_for_the_real_combiner() -> None:
    assert_detector_dominates()  # must not raise


def test_the_dominance_check_actually_fails_a_broken_combiner(monkeypatch: Any) -> None:
    """Without this, `assert_detector_dominates` could be a function that never fails -- which is
    the same failure mode `ADR-013`'s canary test exists for."""

    def vetoing_combine(
        verdict: InjuryVerdict, intent: IntentClassification
    ) -> Any:  # pragma: no cover - the point is that it raises
        from fnol_voice_agent.models.routing import TurnClassification

        # The plausible bad edit: trust a confident classifier over the safety detector.
        suppress = intent.intent_confidence > 0.95
        return TurnClassification(
            safety_flag=verdict.injury_indicated and not suppress,
            intent=intent.intent,
            intent_confidence=intent.intent_confidence,
        )

    monkeypatch.setattr(split_router, "combine", vetoing_combine)
    with pytest.raises(DetectorVetoedError, match="not\n?.*overridable|overridable"):
        assert_detector_dominates()


# --- I1 / Q10: the safety path stays unreachable from the generation-tier flag ---------------------


def test_both_split_calls_are_fixed_to_the_router_model() -> None:
    caller = _split_caller(injury=True)
    classify_turn_split(_turn(), caller=caller)
    assert {call["modelId"] for call in caller.calls} == {ROUTER_MODEL_ID}


def test_the_split_module_never_reads_the_generation_tier_flag() -> None:
    """`ADR-004` made this structural rather than conventional, and the split must not reopen it.
    Checked by source inspection because the guarantee is the *absence* of a code path."""
    import inspect

    source = inspect.getsource(split_router)
    assert "get_generation_model_id" not in source
    assert "GENERATION" not in source.replace("GENERATION_TEMPERATURE", "")


# --- I2: the safety field is required, never defaulted --------------------------------------------


def test_a_detector_response_missing_the_field_raises() -> None:
    """The pre-registration rejected a fail-safe default of `true` **in advance**: it converts a loud
    failure into a silent one and makes false escalation worse. That rejection carries into the split.
    """
    caller = FakeBedrockConverseClient(
        responses=[converse_tool_use_response(DETECT_INJURY_TOOL_NAME, {})]
    )
    with pytest.raises(ValidationError, match="injury_indicated"):
        detect_injury(_turn(), caller=caller)


def test_a_detector_response_with_no_tool_use_block_raises() -> None:
    caller = FakeBedrockConverseClient(responses=[converse_text_response("I'd rather not say")])
    with pytest.raises(BedrockRouterError, match=DETECT_INJURY_TOOL_NAME):
        detect_injury(_turn(), caller=caller)


def test_the_standalone_classifier_call_returns_an_intent_and_a_latency() -> None:
    """`classify_turn_split` submits these very functions to the pool rather than reaching past them
    to the shared call helper, so covering them here covers the concurrent path's legs too."""
    caller = _split_caller(intent="UpdateContactInfo")
    intent, elapsed_ms = classify_intent(_turn("i moved, need to change my address"), caller=caller)
    assert intent.intent is Intent.UPDATE_CONTACT_INFO
    assert elapsed_ms >= 0


def test_the_classifier_schema_has_no_safety_field_to_disagree_with() -> None:
    """Absent, not optional. An optional safety field would give this call a safety opinion the
    combiner would have to weigh, which is the coupling the split exists to remove."""
    schema = IntentClassification.model_json_schema()
    assert "safety_flag" not in schema["properties"]
    assert "injury_indicated" not in schema["properties"]


# --- Rung C's comparability: the injury instruction is copied, not reworded ------------------------


def test_the_verbatim_injury_instruction_is_still_a_substring_of_the_merged_prompt() -> None:
    """Rung C isolates *the merge* only if the words are identical. If someone improves the merged
    prompt without updating this constant, the ladder silently stops being an ablation and starts
    comparing two different instructions -- so this test is the ladder's validity, not a style check.
    """
    assert VERBATIM_INJURY_INSTRUCTION in _CLASSIFY_TURN_SYSTEM_PROMPT


def test_the_detector_prompt_reuses_the_instruction_with_only_the_field_name_changed() -> None:
    expected = VERBATIM_INJURY_INSTRUCTION.replace("`safety_flag`", "`injury_indicated`")
    assert expected in split_router._DETECT_INJURY_SYSTEM_PROMPT
    assert "`safety_flag`" not in split_router._DETECT_INJURY_SYSTEM_PROMPT


def test_the_classifier_prompt_contains_no_injury_guidance() -> None:
    """What is absent is the point: no recall-biased instruction anywhere for a structured-output
    model to make the intent field consistent with."""
    prompt = split_router._CLASSIFY_INTENT_SYSTEM_PROMPT
    for phrase in ("when in doubt", "injury", "unconsciousness", "safety_flag"):
        assert phrase not in prompt


# --- Mechanics -------------------------------------------------------------------------------------


def test_both_calls_force_their_own_tool() -> None:
    caller = _split_caller()
    classify_turn_split(_turn(), caller=caller)
    forced = {call["toolConfig"]["toolChoice"]["tool"]["name"] for call in caller.calls}
    assert forced == {DETECT_INJURY_TOOL_NAME, CLASSIFY_INTENT_TOOL_NAME}


def test_the_raw_classifier_intent_is_preserved_when_the_detector_overrides_it() -> None:
    """`BUILD-PLAN.md` §1 fixed effective-intent scoring before any rung ran, on condition that the
    raw answer is reported alongside -- otherwise the split could be credited by a scoring choice.
    """
    caller = _split_caller(injury=True, intent="CheckClaimStatus")
    result = classify_turn_split(_turn(), caller=caller)
    assert result.classification.intent is Intent.INJURY_ESCALATION
    assert result.raw_intent is Intent.CHECK_CLAIM_STATUS


def test_latency_is_measured_for_both_legs_and_the_wall_clock() -> None:
    caller = _split_caller()
    result = classify_turn_split(_turn(), caller=caller)
    assert result.detector_ms >= 0 and result.classifier_ms >= 0
    assert result.wall_ms >= 0
    # With a fake caller everything is sub-millisecond; the arithmetic relationship is what matters.
    assert result.concurrency_saving_ms == pytest.approx(
        result.detector_ms + result.classifier_ms - result.wall_ms
    )


def test_temperature_zero_is_sent_on_both_legs_by_default() -> None:
    caller = _split_caller()
    classify_turn_split(_turn(), caller=caller)
    assert all(call["inferenceConfig"]["temperature"] == 0.0 for call in caller.calls)


def test_rung_d_can_override_only_the_detector_prompt() -> None:
    caller = _split_caller()
    classify_turn_split(_turn(), caller=caller, detector_prompt="a revised detector prompt")
    systems = [call["system"][0]["text"] for call in caller.calls]
    assert "a revised detector prompt" in systems
    assert split_router._CLASSIFY_INTENT_SYSTEM_PROMPT in systems


# --- The discard bug: a classifier failure must not throw away a resolved safety verdict ----------
#
# Found by the Stage 4 ladder rather than by review. `classify_turn_split` let a classifier
# ValidationError propagate, which discarded a detector verdict that had already arrived on a
# separate connection. The module docstring said graceful degradation was "available" -- it was
# available and not taken, which is the kind of comment that reads as correct forever.


class _ClassifierFailsCaller:
    """Detector answers; classifier returns a tool call missing a required field."""

    def __init__(self, *, injury: bool) -> None:
        self._injury = injury
        self.calls: list[dict[str, Any]] = []
        self._lock = threading.Lock()

    def converse(self, **kwargs: Any) -> dict[str, Any]:
        with self._lock:
            self.calls.append(kwargs)
        tool = kwargs["toolConfig"]["toolChoice"]["tool"]["name"]
        if tool == DETECT_INJURY_TOOL_NAME:
            return _detector(self._injury)
        return converse_tool_use_response(
            CLASSIFY_INTENT_TOOL_NAME, {"intent": "CoverageQuestion"}  # no intent_confidence
        )


def test_a_classifier_failure_does_not_discard_a_fired_detector_verdict() -> None:
    """The turn is fully answerable: a fired detector determines the effective intent by `I3`, so
    the classifier's answer was never going to be used anyway."""
    result = classify_turn_split(_turn(), caller=_ClassifierFailsCaller(injury=True))

    assert result.injury_indicated is True
    assert result.classifier_error is not None
    assert result.classification is not None
    assert result.classification.safety_flag is True
    assert result.classification.intent is Intent.INJURY_ESCALATION
    assert result.raw_intent is None


def test_a_classifier_failure_with_a_silent_detector_yields_no_classification() -> None:
    """The one case with nothing to act on. `None` rather than an invented intent -- the caller's
    retry ladder (`D18`) owns what happens next, and a fabricated intent would route a real caller.
    """
    result = classify_turn_split(_turn(), caller=_ClassifierFailsCaller(injury=False))

    assert result.injury_indicated is False
    assert result.classifier_error is not None
    assert result.classification is None


def test_a_detector_failure_still_raises() -> None:
    """Asymmetric on purpose. A missing safety verdict is not something this function may paper
    over -- there is no answer to degrade gracefully *to*."""

    class DetectorFails:
        def converse(self, **kwargs: Any) -> dict[str, Any]:
            tool = kwargs["toolConfig"]["toolChoice"]["tool"]["name"]
            if tool == DETECT_INJURY_TOOL_NAME:
                return converse_tool_use_response(DETECT_INJURY_TOOL_NAME, {})
            return _classifier()

    with pytest.raises(ValidationError, match="injury_indicated"):
        classify_turn_split(_turn(), caller=DetectorFails())


def test_the_dominance_check_covers_the_absent_classifier_case() -> None:
    """`assert_detector_dominates` gained the None case with this fix. A combiner that returned
    nothing on a fired detector would be suppressing an escalation by omission."""

    def discarding_combine(
        verdict: InjuryVerdict, intent: IntentClassification | None
    ) -> Any:  # pragma: no cover - exists to be rejected
        if intent is None:
            return None  # the bug, in miniature
        return combine(verdict, intent)

    import pytest as _pytest

    with _pytest.MonkeyPatch.context() as mp:
        mp.setattr(split_router, "combine", discarding_combine)
        with pytest.raises(DetectorVetoedError, match="already been resolved"):
            assert_detector_dominates()

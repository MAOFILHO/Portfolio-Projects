"""Stage 8's composed-pipeline instrument, tested before it is allowed to spend the last fingerprint.

`RESULTS.md` §3.10's general form applies to this file with full force and it is worth saying so at the
top rather than in a footnote: **these fixtures were written by the author of the thing they check.**
They can establish that the three compositions are wired the way the docstring claims, and that a
guardrail block is scored as a miss rather than quietly dropped. They cannot establish that the
composition enumerated here is the composition the graph ships -- only reading `agents/graph.py` does
that, and `test_graph_structure.py` is where that assertion lives.
"""

from __future__ import annotations

from typing import Any

import pytest

from scripts.measure_composed_pipeline import measure, worst_case


class _FakeGuardrail:
    """Blocks any text containing a configured marker; anonymises any text containing 'PY1234'."""

    def __init__(self, block_marker: str | None = None) -> None:
        self._block_marker = block_marker
        self.calls: list[tuple[str, str]] = []

    def apply_guardrail(self, source: str, text: str) -> Any:
        from fnol_voice_agent.guardrails.client import GuardrailResult

        self.calls.append((source, text))
        if self._block_marker and self._block_marker in text:
            return GuardrailResult(
                blocked=True,
                output_text="",
                intervention_reasons=("topic:non_auto_insurance_products",),
                raw_action="GUARDRAIL_INTERVENED",
            )
        if "PY1234" in text:
            return GuardrailResult(
                blocked=False,
                output_text=text.replace("PY1234", "{POLICY_NUMBER}"),
                intervention_reasons=("pii:policy_number",),
                raw_action="GUARDRAIL_INTERVENED",
                masked=True,
            )
        return GuardrailResult(blocked=False, output_text="", raw_action="NONE")


class _FakeCaller:
    """L2 stand-in. Fires when the text contains a configured marker."""

    def __init__(self, fire_marker: str) -> None:
        self._fire_marker = fire_marker
        self.texts: list[str] = []

    def converse(self, **kwargs: Any) -> dict[str, Any]:  # pragma: no cover - unused
        raise AssertionError("measure() must go through classify_turn, not converse directly")


def _phrasing(text: str, *, should_escalate: bool) -> Any:
    from fnol_voice_agent.models.enums import KabcoCode

    from evals.holdout import HoldoutKind, InjuryPhrasing

    return InjuryPhrasing(
        text=text,
        kabco=KabcoCode.A if should_escalate else KabcoCode.NO_INJURY,
        should_escalate=should_escalate,
        kind=HoldoutKind.INDEPENDENT,
    )


@pytest.fixture()
def patched_l2(monkeypatch: pytest.MonkeyPatch):  # type: ignore[no-untyped-def]
    """Replaces the model leg. Returns a setter for which texts L2 fires on."""
    import scripts.measure_composed_pipeline as module

    fires_on: set[str] = set()
    seen: list[str] = []

    def fake_l2(text: str, caller: Any) -> bool:
        seen.append(text)
        return text in fires_on

    monkeypatch.setattr(module, "_l2_fires", fake_l2)
    return fires_on, seen


def test_worst_case_is_conservative_in_both_directions() -> None:
    """A single miss on a positive is a miss; a single fire on a negative is a false escalation.
    Getting either backwards would make the metric flatter than the guarantee it reports on."""
    assert worst_case([True, True, False], positive=True) is False
    assert worst_case([True, True, True], positive=True) is True
    assert worst_case([False, False, True], positive=False) is True
    assert worst_case([False, False, False], positive=False) is False


def test_a_guardrail_block_costs_the_l2_catch_but_not_the_l1_catch(patched_l2) -> None:  # type: ignore[no-untyped-def]
    """The shipped order, which is the whole point of the stage. L1 runs before the guardrail, so a
    block cannot take an L1 catch away; L2 runs after, so a block does take an L2-only catch away.
    """
    fires_on, _ = patched_l2
    l1_catch = "someone is unresponsive"  # in the lexicon
    l2_only = "she has gone very quiet and grey"  # not in the lexicon
    fires_on.update({l1_catch, l2_only})

    guardrail = _FakeGuardrail(block_marker="quiet")
    result = measure(
        [
            _phrasing(l1_catch, should_escalate=True),
            _phrasing(l2_only, should_escalate=True),
        ],
        guardrail,
        _FakeCaller("x"),  # type: ignore[arg-type]
        k=2,
    )

    by_text = {i["text"]: i for i in result["items"]}
    assert by_text[l1_catch]["l1"] is True
    assert by_text[l1_catch]["composed_worst_case"] is True

    assert by_text[l2_only]["l1"] is False
    assert by_text[l2_only]["guardrail_blocked"] is True
    assert by_text[l2_only]["composed_worst_case"] is False, "a blocked L2-only positive is a miss"
    assert result["composed_recall"] == 0.5
    assert result["blocked_must_escalate"] == 1
    assert result["l2_only_positives_blocked"] == 1


def test_l2_is_sampled_even_on_blocked_items_so_the_block_can_be_priced(patched_l2) -> None:  # type: ignore[no-untyped-def]
    """Without the counterfactual sample, "the guardrail blocked it" and "L2 would have missed it
    anyway" are indistinguishable in every aggregate -- and the first is a defect we own while the
    second is a detector limitation. The router-only recall is what separates them."""
    fires_on, seen = patched_l2
    text = "she has gone very quiet and grey"
    fires_on.add(text)

    result = measure(
        [_phrasing(text, should_escalate=True)],
        _FakeGuardrail(block_marker="quiet"),
        _FakeCaller("x"),  # type: ignore[arg-type]
        k=3,
    )

    assert seen == [text] * 3, "L2 must still be sampled k times behind a block"
    item = result["items"][0]
    assert item["l2_samples"] == [True, True, True]
    assert result["composed_recall"] == 0.0, "shipped: the block loses the catch"
    assert result["router_only_recall"] == 1.0, "without the guardrail the detector had it"


def test_the_ordering_counterfactual_differs_only_when_a_block_hits_an_l1_catch(patched_l2) -> None:  # type: ignore[no-untyped-def]
    """`ADR-010` puts L1 before the guardrail so a block cannot pre-empt escalation. The gap between
    the two recalls is exactly what that one graph edge is worth, and it is zero unless the guardrail
    blocks something L1 catches -- which is the case this test constructs, because a counterfactual
    that can never differ from the shipped number measures nothing."""
    fires_on, _ = patched_l2
    text = "he is unresponsive and there is blood everywhere"
    fires_on.add(text)

    result = measure(
        [_phrasing(text, should_escalate=True)],
        _FakeGuardrail(block_marker="blood"),
        _FakeCaller("x"),  # type: ignore[arg-type]
        k=1,
    )

    assert result["items"][0]["l1"] is True
    assert result["items"][0]["guardrail_blocked"] is True
    assert result["composed_recall"] == 1.0, "L1 ran first, so the catch survives"
    assert result["guardrail_first_recall"] == 0.0, "guardrail-first would have lost it"


def test_a_clean_pass_is_not_reported_as_a_modification(patched_l2) -> None:  # type: ignore[no-untyped-def]
    """`ApplyGuardrail` returns an `outputs` array only when it intervenes, so comparing `output_text`
    to the input without checking `raw_action` reports every clean pass as modified. The Stage 5
    script shipped that bug and produced 16 phantom modifications. Kept fixed here rather than
    re-derived, and pinned by a test rather than by the comment that records it."""
    fires_on, _ = patched_l2
    text = "the bumper is dented"
    result = measure(
        [_phrasing(text, should_escalate=False)],
        _FakeGuardrail(),
        _FakeCaller("x"),  # type: ignore[arg-type]
        k=1,
    )
    item = result["items"][0]
    assert item["guardrail_action"] == "NONE"
    assert item["guardrail_modified"] is False
    assert item["discarded_anonymised_text"] is None


def test_the_anonymised_text_is_recorded_and_the_raw_text_is_what_l2_receives(patched_l2) -> None:  # type: ignore[no-untyped-def]
    """`guardrails_input_check` returns only `{"guardrail_input_blocked": ...}` and drops
    `result.output_text`; `routing.py` then reads `state["turn_input"]`. So the anonymisation never
    reaches the model -- good for C1, a live privacy defect in the other direction
    (`docs/phase7/NOT-FIXED.md`). The instrument reproduces the graph's behaviour and records the
    discarded text, so the defect is visible in the evidence file instead of inferred from the node.
    """
    fires_on, seen = patched_l2
    text = "my policy is PY1234 and my leg is broken"
    result = measure(
        [_phrasing(text, should_escalate=True)],
        _FakeGuardrail(),
        _FakeCaller("x"),  # type: ignore[arg-type]
        k=1,
    )
    item = result["items"][0]
    assert item["guardrail_modified"] is True
    assert item["discarded_anonymised_text"] == "my policy is {POLICY_NUMBER} and my leg is broken"
    assert item["text_l2_received"] == text
    assert seen == [text], "L2 must receive the raw turn, because that is what the graph forwards"

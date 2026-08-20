"""The two graph nodes that gate every spoken line — untested until Phase 7 Stage 8.

`tests/unit/test_guardrails_client.py` covers the client and hand-rolls `ADR-010`'s four-step sequence
to prove no `guardrailIdentifier` is bolted onto a model call. Nothing imported
`agents/nodes/guardrails_nodes.py`. The sequence was tested; the nodes that implement it were not, and
the branch that decides whether a caller hears the agent's answer or a refusal had no coverage at all.

That is the same shape as `redteam/` shipping unlinted (`RESULTS.md` §5.1) and `fixture_is_stale()`
never existing: the check was written about the thing next to the thing that mattered.
"""

from __future__ import annotations

import json
import logging
from typing import Any

import pytest

from fnol_voice_agent.agents.authority import ELIGIBILITY_DEFLECTION
from fnol_voice_agent.agents.nodes.guardrails_nodes import (
    make_guardrails_input_node,
    make_guardrails_output_node,
)
from fnol_voice_agent.guardrails.client import MockGuardrailClient, MockGuardrailRule

_CLAIM_MASK = MockGuardrailRule(
    pattern=r"CLM-\d{4}-\d{5}-\d",
    reason="regex:claim_number",
    is_regex=True,
    action="MASK",
    replacement="{claim_number}",
)
_VIOLENCE_BLOCK = MockGuardrailRule(pattern="beat him", reason="contentFilter:VIOLENCE")


def _state(**overrides: Any) -> Any:
    base: dict[str, Any] = {"turn_input": "", "contact_id": "test-contact", "filled_slots": {}}
    base.update(overrides)
    return base


def test_a_masked_answer_is_spoken_masked_rather_than_refused() -> None:
    """The Stage 8 defect at the node that exhibited it.

    Before the fix, `blocked` was true for any intervention, so this state produced
    `"I'm sorry, I'm not able to share that -- let me connect you with someone who can help."` The
    agent had looked the claim number up correctly and then refused to say it, and promised a handoff
    it does not perform (`D43`). Forwarding the masked line is strictly better in every case; it is
    still not right, because masking the caller's own claim number back to them is the guardrail
    doing the wrong thing. See `docs/phase7/NOT-FIXED.md`.
    """
    node = make_guardrails_output_node(client=MockGuardrailClient(output_rules=(_CLAIM_MASK,)))
    result = node(_state(response_text="Your claim number is CLM-2608-00042-4."))

    assert result["guardrail_output_blocked"] is False
    assert result["response_text"] == "Your claim number is {claim_number}."


def test_a_genuinely_blocked_answer_is_still_replaced_by_the_fallback() -> None:
    """The mask fix must not weaken the block path -- that would be trading a privacy defect for a
    safety one, which is the trade `C1` and `D13` both forbid."""
    node = make_guardrails_output_node(client=MockGuardrailClient(output_rules=(_VIOLENCE_BLOCK,)))
    result = node(_state(response_text="I will beat him with a hammer."))

    assert result["guardrail_output_blocked"] is True
    assert result["response_text"].startswith("I'm sorry, I'm not able to share that")


def test_a_genuinely_blocked_answer_also_sets_a_real_escalation_record() -> None:
    """`D140`/`OI58`, site 2 (this function's OUTPUT-guardrail-block branch, `:106-107`). Before the fix,
    this branch spoke `_OUTPUT_BLOCKED_FALLBACK`'s "let me connect you with someone" with no
    `EscalationRecord` -- so `D43`'s real Connect-level transfer never fired here. The contrast is a few
    lines up in this same function: `check_authority`'s `violation` branch (`:64-96`) already does this
    correctly, and its own comment names `D43` by number as precisely the mistake this branch was making.
    """
    node = make_guardrails_output_node(client=MockGuardrailClient(output_rules=(_VIOLENCE_BLOCK,)))
    result = node(_state(response_text="I will beat him with a hammer."))

    assert result["guardrail_output_blocked"] is True
    assert result.get("escalation") is not None, (
        "D140/OI58: the OUTPUT-guardrail-block branch promises a transfer but sets no EscalationRecord, "
        "so the real Connect-level transfer built for D43 never fires"
    )
    assert result["escalation"]["route"] == 3
    assert result["escalation"]["triggering_layer"] == "capability"


def test_a_clean_answer_is_left_exactly_as_generated() -> None:
    """No `response_text` key in the returned delta: the node must not rewrite a line it did not
    change. Returning the text unchanged would work today and would quietly become a rewrite the
    first time the client normalises whitespace."""
    node = make_guardrails_output_node(client=MockGuardrailClient(output_rules=(_CLAIM_MASK,)))
    result = node(_state(response_text="Your collision deductible is $500."))

    assert result == {"guardrail_output_blocked": False}


def test_the_authority_check_runs_before_the_guardrail_and_wins() -> None:
    """`ADR-015`: deterministic and free first, so a hit means the billable call is never made. A
    line asserting a settlement violates no content policy and passed the real guardrail in the
    red-team run, so the ordering is the mechanism, not an optimisation."""
    guardrail = MockGuardrailClient(output_rules=(_CLAIM_MASK,))
    calls: list[tuple[str, str]] = []
    original = guardrail.apply_guardrail

    def spy(source: str, text: str) -> Any:
        calls.append((source, text))
        return original(source, text)  # type: ignore[arg-type]

    guardrail.apply_guardrail = spy  # type: ignore[method-assign, assignment]
    node = make_guardrails_output_node(client=guardrail)
    result = node(_state(response_text="Your claim has been approved for $18,000."))

    assert calls == [], "the guardrail must not be called once the authority check has rejected"
    assert result["response_text"] == ELIGIBILITY_DEFLECTION
    assert result["escalation"]["route"] == 3


def test_the_input_node_sends_the_raw_turn_onward_and_reports_only_the_block_decision() -> None:
    """`C1` decision, not an oversight: the detector must see the raw turn. If Bedrock ever masks on
    the input path, writing the masked text back into `turn_input` would hand L2 a turn with spans
    replaced by placeholders -- and L2 is the only detector for 73% of indirect injury phrasing.

    Currently moot and measured rather than assumed: Bedrock does not evaluate the
    sensitive-information policy on `source="INPUT"` at all (verified live against `zl5ppnyorwd2` v2).
    This test is what will fail loudly if someone "fixes" the discard without reading why it is there.
    """
    node = make_guardrails_input_node(
        client=MockGuardrailClient(input_rules=(_CLAIM_MASK,)),
    )
    result = node(_state(turn_input="My claim CLM-2608-00042-4 and my leg is broken."))

    assert result == {"guardrail_input_blocked": False}
    assert "turn_input" not in result


def _guardrail_usage_lines(caplog: pytest.LogCaptureFixture) -> list[dict[str, Any]]:
    return [
        json.loads(r.getMessage().removeprefix("guardrail_usage "))
        for r in caplog.records
        if r.name == "fnol_voice_agent.observability.guardrail_metrics"
    ]


def test_output_node_emits_guardrail_usage_on_a_real_call(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Phase 11 Stage B1: `.usage` used to be discarded entirely (`RESULTS.md` §16.1's finding). This is
    the wiring proof -- a node call that reaches the guardrail must leave exactly one emitted line behind,
    reflecting the real `blocked`/`masked` outcome."""
    caplog.set_level(logging.INFO, logger="fnol_voice_agent.observability.guardrail_metrics")
    node = make_guardrails_output_node(client=MockGuardrailClient(output_rules=(_CLAIM_MASK,)))

    node(_state(response_text="Your claim number is CLM-2608-00042-4."))

    lines = _guardrail_usage_lines(caplog)
    assert len(lines) == 1
    assert lines[0]["source"] == "OUTPUT"
    assert lines[0]["blocked"] is False
    assert lines[0]["masked"] is True


def test_output_node_emits_nothing_when_the_authority_check_short_circuits(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Matches `test_the_authority_check_runs_before_the_guardrail_and_wins`: zero guardrail calls in
    this branch means zero emissions is correct, not a missed wiring site."""
    caplog.set_level(logging.INFO, logger="fnol_voice_agent.observability.guardrail_metrics")
    node = make_guardrails_output_node(client=MockGuardrailClient(output_rules=(_CLAIM_MASK,)))

    node(_state(response_text="Your claim has been approved for $18,000."))

    assert _guardrail_usage_lines(caplog) == []


def test_input_node_emits_guardrail_usage_on_every_call(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO, logger="fnol_voice_agent.observability.guardrail_metrics")
    node = make_guardrails_input_node(client=MockGuardrailClient())

    node(_state(turn_input="a clean turn with no PII"))

    lines = _guardrail_usage_lines(caplog)
    assert len(lines) == 1
    assert lines[0]["source"] == "INPUT"
    assert lines[0]["blocked"] is False
    assert lines[0]["units"] == {}  # MockGuardrailClient never populates usage -- emitted anyway

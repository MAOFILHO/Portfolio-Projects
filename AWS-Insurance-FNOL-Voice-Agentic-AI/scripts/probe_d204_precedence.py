"""`D204`/`OI122` precedence-fix probe (Marco, 2026-08-30) -- does the precedence clause added to
`_CLASSIFY_TURN_SYSTEM_PROMPT` (`aws/bedrock_router.py:56-60`) stop the classifier from reclassifying
a slot-fill answer into a different, unrelated slot-bearing intent (`D204`/`OI122`'s own mechanism --
turn 6 of the fourth live call, `"Comprehensive"` mid-`loss_type` misrouted to `CoverageQuestion`),
without trapping a caller who genuinely changes topic (the risk `D202`/`OI120`'s row explicitly names).

Calls the real, shipped `_build_classify_messages` and `classify_turn` directly -- never a
reimplementation, same discipline as `measure_router_context_latency.py`. No `mock_aws()`; every
call is real and billed under the Bedrock standing cap (`us.amazon.nova-micro-v1:0`,
`ROUTER_TEMPERATURE=0.0`). Read-only probe, no Lex, no Connect, no deploy, per Marco's instruction.

Cases:
  a_repro*  (6)  -- active_slot=loss_type, mid-FileAutoClaim, turn ranging from the original repro
                    ("Comprehensive") through wording that gets progressively closer to real
                    coverage-question phrasing ("is comprehensive covered", "what does comprehensive
                    mean", "collision I think", "will this be covered under comprehensive", "wait,
                    is comprehensive an optional coverage or is it always included"). Expect: stays
                    FileAutoClaim; if any breaks, that phrasing is the finding.
  b_*       (4)  -- same active_slot/state, turn is a genuine topic change: three to a real, different,
                    valid intent (UpdateContactInfo, CheckClaimStatus, RentalTowingEntitlement -- not
                    just the original "speak to a human" reworded) plus the original. Expect: none
                    stay FileAutoClaim -- the fix must not trap a caller who really did change topics.
  c_baseline (1)  -- no active_slot, plain CoverageQuestion phrasing. Expect: unaffected.
"""

from __future__ import annotations

from fnol_voice_agent.agents.nodes.routing import _build_classify_messages
from fnol_voice_agent.aws.bedrock_router import classify_turn

_MID_FAC_SLOT = {
    "active_slot": "loss_type",
    "filled_slots": {"policy_number": "REDACTED", "insured_vehicle_vin": "REDACTED"},
}

CASES: dict[str, dict[str, object]] = {
    "a_repro1_comprehensive": {"turn_input": "Comprehensive", **_MID_FAC_SLOT},
    "a_repro2_is_x_covered": {"turn_input": "is comprehensive covered", **_MID_FAC_SLOT},
    "a_repro3_what_does_x_mean": {"turn_input": "what does comprehensive mean", **_MID_FAC_SLOT},
    "a_repro4_x_i_think": {"turn_input": "collision I think", **_MID_FAC_SLOT},
    "a_repro5_will_this_be_covered": {
        "turn_input": "will this be covered under comprehensive",
        **_MID_FAC_SLOT,
    },
    "a_repro6_optional_or_included": {
        "turn_input": "wait, is comprehensive an optional coverage or is it always included",
        **_MID_FAC_SLOT,
    },
    "b_escape1_speak_to_human": {
        "turn_input": "actually, can I speak to a human about something else",
        **_MID_FAC_SLOT,
    },
    "b_escape2_update_contact": {
        "turn_input": "actually never mind the claim, can you update my phone number instead",
        **_MID_FAC_SLOT,
    },
    "b_escape3_check_other_claim": {
        "turn_input": "sorry, I actually need to check on a different claim I already filed",
        **_MID_FAC_SLOT,
    },
    "b_escape4_rental_question": {
        "turn_input": "forget the claim, can you tell me if my policy covers rental cars",
        **_MID_FAC_SLOT,
    },
    "c_baseline": {
        "turn_input": "does my policy cover a rental car while mine's in the shop",
        "active_slot": None,
        "filled_slots": {},
    },
}


def _selfcheck() -> None:
    """Offline, no network: `_build_classify_messages` folds `active_slot` in for a/b and not c,
    the one piece of this script's own wiring that a live-call result can't distinguish from a
    prompt-behavior change if it were silently broken."""
    a_text = _build_classify_messages(CASES["a_repro1_comprehensive"])[0]["content"][0]["text"]
    assert "Currently eliciting slot: loss_type" in a_text, a_text
    c_text = _build_classify_messages(CASES["c_baseline"])[0]["content"][0]["text"]
    assert "Currently eliciting slot" not in c_text, c_text


def main() -> None:
    _selfcheck()
    for name, state in CASES.items():
        messages = _build_classify_messages(state)
        result = classify_turn(messages)
        print(
            f"{name}: intent={result.intent.value} "
            f"confidence={result.intent_confidence} "
            f"safety_flag={result.safety_flag} "
            f"coverage_question_type={result.coverage_question_type.value}"
        )


if __name__ == "__main__":
    main()

"""`agents/nodes/update_contact_info.py` -- previously only exercised indirectly, through
`tests/unit/test_graph_integration.py`'s happy-path turns and `test_lex_codehook.py`. Neither ever drove
this node into its confirm-ceiling-exhausted branch, so `D140`/`OI58`'s gap there had no direct test at
all until this file.
"""

from __future__ import annotations

from typing import Any

from fnol_voice_agent.agents.nodes.update_contact_info import update_contact_info_node

_FILLED = {
    "policy_number": "PY4821",
    "field": "phone",
    "new_value": "647-321-9876",
}


def _state(**overrides: Any) -> Any:
    base: dict[str, Any] = {
        "contact_id": "test-contact",
        "filled_slots": dict(_FILLED),
        "retry_counts": {},
    }
    base.update(overrides)
    return base


def test_confirm_ceiling_exhausted_escalates_with_a_real_escalation_record() -> None:
    """`D140`/`OI58`, site 3 (`_CONFIRM_CEILING`-exhausted branch, `:59-63`). `DIALOGUE-POLICIES.md` §4's
    tighter one-retry ceiling means this branch fires on the SECOND failed confirmation: `retry_counts`
    already carries one prior failed attempt (`confirm_update_contact_info: 1`), and this turn's own
    "no" pushes the count to 2, over `_CONFIRM_CEILING = 1`. Before the fix, this branch spoke
    `_ESCALATION_SCRIPT`'s "let me connect you with someone" with no `EscalationRecord` -- so `D43`'s
    real Connect-level transfer never fired here either. `agents/nodes/repair.py`'s
    `handle_no_match_or_barge_in` is the correct reference implementation for the same shape.
    """
    state = _state(
        filled_slots={**_FILLED, "confirm_update_contact_info": False},
        retry_counts={"confirm_update_contact_info": 1},
    )

    result = update_contact_info_node(state)

    assert "let me connect you with someone" in result["response_text"].lower()
    assert result.get("escalation") is not None, (
        "D140/OI58: the _CONFIRM_CEILING-exhausted branch promises a transfer but sets no "
        "EscalationRecord, so the real Connect-level transfer built for D43 never fires"
    )
    assert result["escalation"]["route"] == 3
    assert result["escalation"]["triggering_layer"] == "capability"


def test_a_single_failed_confirmation_is_a_reprompt_not_an_escalation() -> None:
    """Sibling case, same seam: the FIRST failed confirmation (no prior retry_counts entry) must still
    be the plain reprompt-and-retry path, not escalate early. `_CONFIRM_CEILING = 1` means exactly one
    retry is allowed before this test's sibling above kicks in."""
    state = _state(filled_slots={**_FILLED, "confirm_update_contact_info": False})

    result = update_contact_info_node(state)

    assert "is that right" in result["response_text"].lower()
    assert result.get("escalation") is None
    assert result["retry_counts"]["confirm_update_contact_info"] == 1

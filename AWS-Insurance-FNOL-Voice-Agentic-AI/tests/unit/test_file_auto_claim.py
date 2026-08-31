"""`agents/nodes/file_auto_claim.py` -- `_next_missing_slot` specifically. Previously only exercised
indirectly, through `test_graph_integration.py`'s happy-path turns, none of which ever put a spurious
value in `filled_slots` the way a live call can.
"""

from __future__ import annotations

from fnol_voice_agent.agents.nodes.file_auto_claim import _next_missing_slot

# All ten `_SLOT_ORDER` slots present and valid except `insured_vehicle_vin` -- everything but VIN
# already "answered" ensures a false pass here (returning `None`) can only be `_next_missing_slot`
# treating the spurious VIN as filled, not some other slot the loop hadn't reached yet.
_FILLED_EXCEPT_VIN = {
    "policy_number": "PY4821",
    "loss_datetime": "2026-08-29T09:00:00-04:00",
    "loss_location": "Innisfil, Ontario",
    "loss_type": "Comprehensive",
    "damage_description": "Rear bumper and tail light",
    "other_party_involved": False,
    "police_report_filed": False,
    "driver_name": "Marco",
}


def test_a_spurious_vin_is_not_treated_as_an_answer() -> None:
    """Live repro (contacts `fee42379-c6a9-4eaa-94d4-be20b355c400`,
    `4c968199-218f-42dd-9f68-834947f3902b`): Lex's own whole-utterance NLU opportunistically resolved
    `insured_vehicle_vin` to something that was never a real 17-character VIN -- 12 characters here, the
    same shape as the live case. `_next_missing_slot` must not treat that as an answer just because it is
    non-`None`; a value that cannot possibly be a valid VIN is not a filled slot.
    """
    filled = {**_FILLED_EXCEPT_VIN, "insured_vehicle_vin": "ABCDEFGHIJKL"}  # 12 chars, not 17

    assert _next_missing_slot(filled) == "insured_vehicle_vin"


def test_a_correctly_shaped_vin_is_treated_as_an_answer() -> None:
    """Sibling case, same seam: a real 17-character VIN must still count as filled -- this fix narrows
    what counts as an answer, it does not stop accepting real ones."""
    filled = {**_FILLED_EXCEPT_VIN, "insured_vehicle_vin": "9SYAB1239G1000101"}  # 17 chars

    assert _next_missing_slot(filled) is None

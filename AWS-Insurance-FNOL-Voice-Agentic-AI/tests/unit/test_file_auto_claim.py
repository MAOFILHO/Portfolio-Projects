"""`agents/nodes/file_auto_claim.py` -- `_next_missing_slot` specifically. Previously only exercised
indirectly, through `test_graph_integration.py`'s happy-path turns, none of which ever put a spurious
value in `filled_slots` the way a live call can.
"""

from __future__ import annotations

import re

from fnol_voice_agent.agents.nodes.file_auto_claim import (
    _next_missing_slot,
    _vehicle_choices_prompt,
    file_auto_claim,
)
from fnol_voice_agent.mcp.claims_server import resolve_vehicle_description, vehicles_for_policy

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


# ---------------------------------------------------------------------------------------------------
# `D207`/`OI125` direction 3: telephony ASR cannot transcribe "Meridian" -- three live diagnostic rounds
# confirmed the model name never arrives, so the open "which vehicle" question is replaced with reading
# the caller's own vehicles back. PY4821 (real corpus fixture) has two vehicles -- 2022 Example Motors
# Meridian (9SYAB1239G1000101), 2024 Harborline Skiff (9SYNP3452H2000501); PY1103 has exactly one -- 2019
# Example Motors Comet (9SYCD4568G1000102).
# ---------------------------------------------------------------------------------------------------


def test_a_two_vehicle_policy_gets_an_enumerated_selection_prompt() -> None:
    result = file_auto_claim(
        {"filled_slots": {"policy_number": "PY4821"}, "active_slot": "policy_number"}
    )

    assert result["active_slot"] == "insured_vehicle_vin"
    assert result["response_text"] == "Is this about the 2022 Meridian, or the 2024 Skiff?"


def test_an_unresolvable_policy_number_is_re_asked_not_the_vehicle_question() -> None:
    """`D207`/`OI125` follow-up, live evidence 2026-09-02 (contacts `07ec07e6`/`f5cd57b9`): 'py'/'py48'
    (ASR-truncated) leave `vehicles_for_policy` empty -- zero vehicles, not one or two. Before this fix,
    `_vehicle_choices_prompt`'s under-2-vehicle fallback treated that identically to a real single- or
    zero-vehicle policy and asked the open vehicle question ("Which vehicle...?") -- unanswerable, since
    the caller can never name a vehicle for a policy number that never resolved. `policy_number` itself
    must be re-asked instead, the same way a malformed VIN is treated as unanswered rather than accepted.
    """
    result = file_auto_claim(
        {"filled_slots": {"policy_number": "py48"}, "active_slot": "policy_number"}
    )

    assert result["active_slot"] == "policy_number"
    assert result["response_text"] == "What's your policy number?"


def test_a_single_vehicle_policy_is_never_asked_about_at_all() -> None:
    """`D207`/`OI125` direction 3, item 3: a policy with exactly one vehicle skips the question --
    filled and moved past in the same turn `policy_number` itself was answered."""
    result = file_auto_claim(
        {"filled_slots": {"policy_number": "PY1103"}, "active_slot": "policy_number"}
    )

    assert result["filled_slots"]["insured_vehicle_vin"] == "9SYCD4568G1000102"
    assert result["active_slot"] == "loss_datetime"  # the NEXT slot -- VIN was never asked


def test_ordinal_resolution_matches_the_prompts_own_reading_order() -> None:
    """Nothing today enforces that `_match_by_ordinal` (claims_server.py) counts positions in the same
    order `_vehicle_choices_prompt` reads them back in -- both happen to start from `vehicles_for_policy`,
    so "the first one" resolves to the right vehicle by construction, not by a checked contract. If either
    one ever sorted its list and the other didn't, "the first one" would file a claim against the wrong
    vehicle, silently. A hardcoded expected VIN here would keep passing through that divergence -- it was
    only ever checking today's coincidence, not the contract. This test instead builds the real prompt,
    parses the model names out of the prompt TEXT in the order they appear, and checks that "the first
    one" resolves to whichever vehicle's model appeared first there. It fails the moment the two orders
    disagree.
    """
    vehicles = vehicles_for_policy("PY4821")
    prompt = _vehicle_choices_prompt({"policy_number": "PY4821"})

    model_positions = {
        match.start(): vehicle
        for vehicle in vehicles
        for match in re.finditer(re.escape(vehicle.model), prompt)
    }
    first_vehicle_in_prompt = model_positions[min(model_positions)]

    assert resolve_vehicle_description("the first one", "PY4821") == first_vehicle_in_prompt.vin

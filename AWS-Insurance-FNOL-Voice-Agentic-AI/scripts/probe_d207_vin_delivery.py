"""`D207`/`OI125` follow-up probe (Marco, 2026-09-01) -- two live calls escalated on `insured_vehicle_vin`
even though the caller answered with the vehicle's real model name ("The Meridian", "Meridian",
"2022 Meridian"). `resolve_vehicle_description` passes all 8 of its own unit tests against exactly this
phrasing, so the open question is not "does the resolver work" -- it's "did the resolver ever SEE real
text". The per-turn CloudWatch log line (`_log_turn_observability`) can't answer that after `D207`/`OI125`
Change 1 shipped: it logs `insured_vehicle_vin_len` off `result['filled_slots']`, which Change 1 now POPS
on any unresolved value -- so `None` there means "nothing arrived" and "garbage arrived but didn't
resolve" are logged identically. `lex_slot_keys` doesn't help either: Lex's own slots dict carries every
declared FileAutoClaim slot NAME whether or not that slot has a value this turn, so the key's presence in
that log field proves nothing about whether `insured_vehicle_vin` actually carried a value.

**Read-only, no edits, no deploy, per Marco's instruction.** Calls the REAL deployed bot end to end --
real Lex NLU, real deployed `fnol-codehook` Lambda, real `resolve_vehicle_description` -- via
`lexv2-runtime.recognize_text`, exactly the transport `verify_row9_layer1_escalation_wire.py::recognize_live`
already established and `measure_composed_pipeline_deployed.py::recognize` already runs routinely under
this project's normal operating cost (`ADR-013`: every real `RecognizeText` call is billed, however
negligibly -- $0.00075/text call per `PROJECT_STATE.md`'s verified pricing table; this probe makes 15
calls, ~$0.011 total). Fresh `sessionId` per phrasing -- five independent 3-turn conversations, not one
long one, so an earlier phrasing's retry count can never leak into a later one.

WHAT THIS DISTINGUISHES, AND HOW
    Reads `sessionState.intent.slots.insured_vehicle_vin.value.interpretedValue` off turn 3's OWN
    response -- not the resolver's output, the RAW value Lex assigned this turn. This is sound because
    `_elicit_slot` (`api/lex_codehook.py:470-527`) builds its outgoing `slots` map by filtering THIS
    SAME TURN's incoming `_intent_from(event).get('slots')` down to the keys legal for the graph's
    intent (`:513-514`) -- it drops illegal KEYS, it never rewrites a surviving key's VALUE. Since
    `insured_vehicle_vin` is always legal for `FileAutoClaim`, whatever Lex delivered for it this turn
    survives untouched into the echoed response, regardless of whether resolution succeeded or failed.
    `sessionState.dialogAction.slotToElicit` on that same response says which: `insured_vehicle_vin`
    again means resolution failed (a reprompt); `loss_datetime` (the next slot in `_SLOT_ORDER`) means it
    succeeded.

    Three-way split per phrasing:
      - raw interpretedValue is None/absent  -> Lex never delivered a value. The resolver is irrelevant;
        `AMAZON.FreeFormInput` did not fill on this turn. (Docs: "only recognized when elicited for" --
        if turn 2's own response didn't set `slotToElicit=insured_vehicle_vin`, this precondition failed
        and is reported separately, not folded into this bucket.)
      - raw interpretedValue is close to the spoken text but resolution still failed -> ASR/NLU altered
        the words enough that `resolve_vehicle_description`'s word-boundary match on the real corpus
        (PY4821: 2022 Example Motors Meridian, VIN 9SYAB1239G1000101) legitimately doesn't match --
        an ASR problem, not a slot-delivery or resolver problem.
      - raw interpretedValue reads as "Meridian" (or a superset) and resolution still failed -> the
        resolver itself has a live-vs-test discrepancy -- the one bucket that would mean Change 1's own
        code, not its precondition, is broken.
"""

from __future__ import annotations

import json
import subprocess
import uuid
from pathlib import Path
from typing import Any

import boto3

REPO_ROOT = Path(__file__).resolve().parents[1]
STACK_DIR = REPO_ROOT / "infra" / "terraform" / "stacks" / "main"
LOCALE_ID = "en_US"
REGION = "us-west-2"

# PY4821's real corpus fixture (`data/synthetic/vehicles/vehicles.json`) -- same fixture
# `test_mcp_claims_server.py`'s resolver unit tests use. "PY4821" alone, not a full sentence: the
# policy_number slot is `AMAZON.AlphaNumeric` (`bot.yaml.tftpl:261`), and a bare value is the
# unambiguous, already-proven-working answer shape (`test_lex_codehook.py`'s own multi-turn tests).
_POLICY_NUMBER = "PY4821"
_EXPECTED_VIN = "9SYAB1239G1000101"

# Matches an actual FileAutoClaim SampleUtterance (`bot.yaml.tftpl:8`) -- not paraphrased, so a failure
# here can't be blamed on this probe's own wording of turn 1.
_OPEN_UTTERANCE = "I need to file a claim"

PHRASINGS: tuple[str, ...] = (
    "The Meridian",
    "Meridian",
    "2022 Meridian",
    "the 2022 Example Motors Meridian",
    "Example Motors Meridian",
)


def terraform_outputs(stack_dir: Path = STACK_DIR) -> dict[str, Any]:
    result = subprocess.run(
        ["terraform", f"-chdir={stack_dir}", "output", "-json"],
        capture_output=True,
        text=True,
        check=True,
    )
    return {k: v["value"] for k, v in json.loads(result.stdout).items()}


def _slot_interpreted_value(response: dict[str, Any], slot_name: str) -> str | None:
    slots = ((response.get("sessionState") or {}).get("intent") or {}).get("slots") or {}
    slot = slots.get(slot_name)
    if not isinstance(slot, dict):
        return None
    value = slot.get("value")
    if not isinstance(value, dict):
        return None
    interpreted = value.get("interpretedValue")
    return interpreted if isinstance(interpreted, str) else None


def _slot_to_elicit(response: dict[str, Any]) -> str | None:
    slot_to_elicit = (
        (response.get("sessionState") or {}).get("dialogAction", {}).get("slotToElicit")
    )
    return slot_to_elicit if isinstance(slot_to_elicit, str) else None


def _message(response: dict[str, Any]) -> str:
    messages = response.get("messages") or []
    return messages[0].get("content", "") if messages else ""


def probe_one(runtime: Any, *, bot_id: str, bot_alias_id: str, vehicle_text: str) -> dict[str, Any]:
    session_id = f"d207-vin-delivery-{uuid.uuid4()}"

    runtime.recognize_text(
        botId=bot_id,
        botAliasId=bot_alias_id,
        localeId=LOCALE_ID,
        sessionId=session_id,
        text=_OPEN_UTTERANCE,
    )
    r2 = runtime.recognize_text(
        botId=bot_id,
        botAliasId=bot_alias_id,
        localeId=LOCALE_ID,
        sessionId=session_id,
        text=_POLICY_NUMBER,
    )
    precondition_ok = _slot_to_elicit(r2) == "insured_vehicle_vin"

    r3 = runtime.recognize_text(
        botId=bot_id,
        botAliasId=bot_alias_id,
        localeId=LOCALE_ID,
        sessionId=session_id,
        text=vehicle_text,
    )
    raw_value = _slot_interpreted_value(r3, "insured_vehicle_vin")
    next_slot = _slot_to_elicit(r3)
    resolved = next_slot != "insured_vehicle_vin"

    return {
        "phrasing": vehicle_text,
        "session_id": session_id,
        "precondition_ok": precondition_ok,
        "turn2_slot_to_elicit": _slot_to_elicit(r2),
        "raw_interpreted_value": raw_value,
        "resolved": resolved,
        "turn3_slot_to_elicit": next_slot,
        "turn3_message": _message(r3),
    }


def main() -> None:
    outputs = terraform_outputs()
    bot_id = outputs["bot_id"]
    bot_alias_id = outputs["bot_alias_id"]
    runtime = boto3.client("lexv2-runtime", region_name=REGION)

    print(f"bot_id={bot_id} bot_alias_id={bot_alias_id} region={REGION}")
    print(f"expecting VIN {_EXPECTED_VIN} (PY4821's 2022 Example Motors Meridian)\n")

    for phrasing in PHRASINGS:
        result = probe_one(runtime, bot_id=bot_id, bot_alias_id=bot_alias_id, vehicle_text=phrasing)
        print(f"phrasing={phrasing!r}")
        print(f"  precondition (turn2 elicited insured_vehicle_vin): {result['precondition_ok']}")
        print(f"  raw interpretedValue Lex returned: {result['raw_interpreted_value']!r}")
        print(f"  resolved: {result['resolved']}")
        print(f"  turn3 slotToElicit: {result['turn3_slot_to_elicit']!r}")
        print(f"  turn3 message: {result['turn3_message']!r}")
        print(f"  session_id: {result['session_id']}\n")


if __name__ == "__main__":
    main()

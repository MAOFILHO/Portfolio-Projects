"""The permanent deploy-time execution gate — `D80`/`D81`, `docs/phase8/STAGE4-LAMBDA-LAYER-PLAN.md` §4.

WHY THIS EXISTS, AND WHY IT IS NOT THE D77-STYLE READ-BACK
    `D80`: a Lambda deploy was verified by reading back `LastUpdateStatus: Successful`, `State: Active`,
    and a bit-for-bit `CodeSha256` match — real checks, and none of them execute the function. The
    deployed code crashed on its own first `import` statement on 100% of its invocations the entire time
    it was live, and that read-back could not have caught it, structurally, because it never asked the
    function to run. This script asks it to run. `RESULTS.md` §11.1: *"a deployment-verification check
    that reads service-reported deploy status, however rigorously, is necessary and not sufficient... The
    sufficient check invokes the function and reads its output."* This is that check.

WHY IT DOES NOT TRUST A BARE `StatusCode: 200`
    `lambda:Invoke`'s synchronous response carries `StatusCode: 200` for both a normal return AND an
    unhandled exception in the function — `D80`'s own diagnostic call (`RecognizeText`, one layer up at
    the Lex boundary) never raised either, for the identical reason: a codehook that crashes at cold
    start still produces a normal-looking response at the boundary that invoked it. The real signal is a
    separate `FunctionError` field (`"Unhandled"`/`"Handled"`) plus a structured error object in the
    payload body. Every event below is checked in order: (a) `FunctionError` absent from the `Invoke`
    response, checked first and explicitly; (b) the payload parses as JSON and carries a legal
    `sessionState.dialogAction.type` (`Delegate`/`ElicitSlot`/`Close`) — a well-formed body with the
    wrong shape (Lambda's own `errorMessage`/`errorType` JSON, which *is* valid JSON) fails here; (c) a
    literal marker specific to the exercised path, proving the intended branch of `_dispatch()` ran, not
    merely that *some* branch returned *something*.

THE EVENT MATRIX — 9 EVENTS, NOT THE 10 THE FIRST DRAFT OF THIS PLAN NAMED
    Plan §4's first draft said "each of the six in-scope intents' first turn." That overcounts by one:
    `CLAUDE.md`'s sixth in-scope intent is "injury or fatality mentioned," and `aws/bedrock_router.py`
    deliberately has NO `InjuryEscalation` value in its classifier's intent enum (`ADR-010`'s dominance
    requirement — injury is never something the router classifies a turn INTO, it is a safety flag plus
    the separate pre-graph L1 check). There is no "InjuryEscalation intent's first turn via ordinary
    classification" event to construct, because that code path does not exist; the raw-text L1 trigger
    event below already exercises the intent's only two entry points structurally available (pre-graph
    L1 raw text, and the graph's own in-band `L2` safety-flag branch, exercised indirectly since a
    genuinely dangerous-sounding FIRST turn for any intent would hit one of the two). Nine, not ten:

    1-5. The five ORDINARY intents' first turn (`FileAutoClaim`, `CheckClaimStatus`, `CoverageQuestion`,
         `RentalTowingEntitlement`, `UpdateContactInfo`) — canonical opener utterances taken verbatim
         from `bot.yaml.tftpl`'s own declared sample utterances, to minimise live-router classification
         variance rather than inventing phrasing the bot was never tuned against. Marker: `ElicitSlot`
         targeting the specific first slot each graph node (`agents/nodes/*.py`) asks for on an empty
         `filled_slots` — read from the NODE's own priority order, not Lex's declared `SlotPriorities`,
         because `api/lex_codehook.py`'s own docstring states the response shape is a function of the
         GRAPH's state, never Lex's own slot walk (`D78`).
    6.   `FallbackIntent` — a deliberately unclassifiable utterance. Marker: `Close` (not `ElicitSlot` --
         `handle_no_match_or_barge_in` never sets `active_slot` on a first-attempt no-match) with the
         exact fixed `GENERIC_REPROMPT` string (`agents/nodes/repair.py`) and no `escalate` attribute.
    7.   Raw-text L1 trigger (pre-graph, bypasses the graph and the checkpointer entirely).
    8.   Raw-text L3 trigger (pre-graph, the `D74` agent-override lexicon).
    9.   `injuries_present` confirmed True with no injury vocabulary in the raw text (`D79`).

    Events 7-9 are genuinely Bedrock-free (pre-graph, deterministic pattern matching, at most one
    checkpointer read). **Events 1-6 are NOT** — every turn that reaches the graph passes through
    `guardrails_input_check` (`ApplyGuardrail`) and `route_and_classify` (`classify_turn`, a real
    Bedrock Converse call) unconditionally, regardless of which intent Lex's own NLU already guessed;
    `agents/nodes/routing.py`'s own docstring confirms this runs on every turn that reaches it. Plan
    §4's first draft claimed "no Bedrock reached by any synthetic event" — checked against the actual
    graph code while writing this script, and it does not hold for 6 of the 9 events. Real, small cost:
    ~$0.0003/call (guardrail, 2 units) plus a fraction of a cent (Nova Micro router, a short prompt) per
    event, roughly **$0.002 total** for this script's own run, not the $0.00 the plan first claimed.
    Genuinely negligible against the $25 ceiling, but the CLAIM was wrong and is corrected here rather
    than left standing, same discipline as `D80`'s own "comment-as-evidence" finding.

    **Consequence stated plainly: this is NOT a pure liveness check.** A pure liveness check asks one
    question -- did the function execute -- and every event would be free to construct because none would
    depend on model behavior. 6 of these 9 events are not that: a FAILURE on one of them is ambiguous
    between (1) a `D80`-shaped infra regression and (2) an ordinary model-classification miss that has
    nothing to do with whether the Lambda executes. Only the 3 pre-graph events (L1, L3, `D79`) are pure
    liveness checks in the strict sense. Check WHICH event failed before concluding `D80` recurred.

STANDING-APPROVAL SCOPE — FLAGGED, NOT RESOLVED, HERE
    `CLAUDE.md`'s Bedrock standing approval is worded *"for Phases 3-7, capped at $5 total."* This
    script's own Bedrock spend happens in Phase 8. Whether that approval's scope extends past the phase
    range in its own wording, or a fresh approval / an explicit extension is needed, is Marco's call, not
    assumed either way by this script. **For that reason this target is deliberately NOT chained into
    `make deploy`** in this pass, despite plan §4 proposing exactly that -- it is `make
    verify-lambda-execution`, invocable on its own, so running it (and incurring its small real Bedrock
    spend) is always a separate, visible decision until that scope question is settled.

`ADR-013`: no `mock_aws()` in this file. Every `Invoke` call is real; 6 of the 9 events also make real,
billed Bedrock calls one layer down (see above).

EVENTS 10-11 -- `D87`'S SCOPED REGRESSION TEST, ADDED 2026-08-16 (`RESULTS.md` §30, Marco-approved)
    `D87`: real fulfillment for `CheckClaimStatus`, `RentalTowingEntitlement`, `FileAutoClaim`, and
    `UpdateContactInfo` was broken in the deployed artifact -- `_paths.py`'s `parents[3]` climb resolves to
    a directory that does not exist under `/var/task` in Lambda, one level shallower than local dev.
    Events 1-6 above never caught it because every one of them stops at the FIRST `ElicitSlot` -- none
    supplies enough slots to reach the code path that reads `data/synthetic/` at all. That is `D87`'s own
    "transferable finding": a script can invoke the real deployed Lambda nine times and never touch the
    line that crashed on 100% of real calls.

    Events 10-11 close that gap for two of the four confirmed-broken intents, by supplying every slot a
    real multi-turn conversation would have filled by the time the affected code path runs -- same
    technique `scripts/verify_stage_b1_live_invoke.py` and `scripts/verify_d87_scope.py` used to find and
    scope `D87` in the first place, folded into the PERMANENT gate here rather than left as one-off
    scripts, so no future redeploy can regress this silently the way this one did. `RentalTowingEntitlement`
    and `FileAutoClaim` are not covered here -- `CF8` (`PROJECT_STATE.md`) is the generalized version that
    would close the remaining gap; these two are the concrete instances of `CF8` Marco named explicitly
    when `D87` was scoped.

    RED-GREEN, NOT WRITE-AND-TRUST: this project's own discipline (`CLAUDE.md`'s pre-commit-hook and
    Stage C filter precedent) is that a test which has only ever been observed passing proves nothing.
    Events 10-11 were run against the pre-fix build first and confirmed to FAIL with the exact
    `FileNotFoundError` `D87` names, before Option A was applied -- see `RESULTS.md` §30/§31 for the red
    and green transcripts side by side.

EVENTS 12-13 -- `FileAutoClaim`/`RentalTowingEntitlement`, ADDED 2026-08-16 (`RESULTS.md` §33, tightening
`D87`'s closure per Marco)
    `D87`'s own close (§32) reached real fulfillment for `CheckClaimStatus` and `UpdateContactInfo` (events
    10-11) and separately confirmed `policy_server.py`'s latent crash MOOT -- but stopped there, on the
    stated reasoning that `FileAutoClaim` and `RentalTowingEntitlement` share the identical root cause and
    fix. Shared import did not establish shared reachability for `policy_server.py` in the very same
    investigation (`RESULTS.md` §31/§32) -- inferring these two intents are fixed from the other two being
    fixed is the same shape of unearned claim, just not caught before D87/OI4 was marked CLOSED. These two
    events close that gap for real rather than leaving it as inference. Real slot data from `data/synthetic/`
    (`PY4821`, VIN `9SYAB1239G1000101`, policy PY4821's own name/loss facts) -- same reuse discipline as
    events 10-11's claim/policy numbers, so a disagreement in outcome would itself be a signal.

    `FileAutoClaim` (event 12) reaches `claims_server.file_new_claim`, which reads `POLICYHOLDERS_PATH` and
    `VEHICLES_PATH` -- `D87`'s exact crash site -- then writes to an in-memory, per-process
    `_filed_claims` dict (`claims_server.py`'s own comment: "no real persistence layer yet"), never back to
    `CLAIMS_PATH` on disk. Safe to run repeatedly as a permanent gate event: no mutation of the deployed
    artifact's data, and `_next_claim_number`'s sequence counter is seeded from the real corpus's own max
    per month, so a collision with a fixture claim number is structurally impossible. Marker: `Close`/
    `Fulfilled`, message contains the node's fixed `"Your claim number is "` prefix template
    (`agents/nodes/file_auto_claim.py`) followed by a real `CLM-YYMM-NNNNN-C`-shaped number. The freshly
    generated claim number is asserted PRESENT verbatim, not masked -- learned directly from `D88` (see
    that finding's own section below): the regex-based claim-number PII entity was removed at the
    guardrail's v2->v3 change, Marco-approved, specifically because masking a caller's own identifier back
    to them is a defect, not a protection. Asserting the opposite here would repeat `D88`'s own mistake in
    a new event on the same day it was found.

    `RentalTowingEntitlement` (event 13) reaches `claims_server.get_claim_status` (same `CLAIMS_PATH` read)
    and, for a resolved claim with rental elected, `get_rental_status` -- then a REAL Bedrock `Converse`
    call (`generate_response`) over the retrieved policy text and the claim/rental facts. This is the one
    event in the whole matrix whose final response text is genuinely model-generated, not a fixed template
    -- so the check below asserts only the structural markers a crash would flip (`Close`/`Fulfilled`,
    non-empty message, not the node's own fixed `_ABSTENTION` string), not the generated wording itself.
    Asserting exact content here would be the same category error as `D88` in the other direction: treating
    an activity signal (the model produced *some* text) as an effect signal would be too weak, but
    over-asserting on non-deterministic content would make this check flaky for reasons that have nothing
    to do with `D87`. The structural markers are exactly what a `_paths.py`-shaped crash would flip, which
    is what this event exists to catch.

    NOT INDEPENDENTLY RED-GREEN'D AGAINST THE PRE-FIX BUILD, STATED PLAINLY: unlike events 10-11, these two
    were never run against the pre-fix artifact -- doing so would require redeploying the known-broken build
    over the current fixed one, a real, disruptive, costly action nobody asked for just to re-derive a
    result already established for the identical code path (events 10-11 already proved, red then green,
    that a pre-`_paths.py`-fix build raises `FileNotFoundError` inside every one of `claims_server.py`'s and
    `contact_server.py`'s `_load_*`/`*_PATH.read_text()` call sites, and events 12-13 exercise the same
    `_load_claims`/`_load_vehicles`/`POLICYHOLDERS_PATH` sites in the same module). This is reasoning from
    an already-demonstrated failure on the same code, not a fresh, unearned green -- but it is reasoning,
    not a second empirical red, and that distinction is recorded here rather than left implicit.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import boto3

REPO_ROOT = Path(__file__).resolve().parents[1]
STACK_DIR = REPO_ROOT / "infra" / "terraform" / "stacks" / "main"
REGION = "us-west-2"

_MINIMUM_EVENTS = (
    13  # `--require-at-least 1`'s cousin, `check_flows.py`'s discipline: finding nothing
)
# must never read as passing. A matrix that silently shrank to zero entries would otherwise report
# "0/0 passed" and exit 0. Raised 9->11 for events 10-11, `D87`'s scoped regression test; 11->13 for
# events 12-13, tightening D87's closure to the two intents it was inferred-not-verified for.

# Estimated, not exact -- printed before any call is made, same cost-gate discipline as every other
# script in this repo that spends real money. See the module docstring's cost section for the basis.
# Deliberately NOT a hardcoded "N events reach Bedrock" constant next to this one, the way this file used
# to compute it before 2026-08-16 -- that constant (`_ESTIMATED_GUARDRAIL_CALLS = 6`) went stale the
# moment events 10-11 were added below and would have silently under-reported cost from here on with no
# signal that it had. `main()` now derives it from the real matrix every run instead, so it cannot drift
# again the same way. `_GUARDRAIL_PER_CALL_USD` itself is a real-world rate (2 policy units per
# `ApplyGuardrail` call), not a per-event figure -- see `main()`'s use of it below.
_GUARDRAIL_PER_CALL_USD = 2 * 0.15 / 1000

# Event 13's real `generate_response` call, on top of the guardrail+router cost every Bedrock-reaching
# event already carries. Rough upper bound, not measured: ~800 input / ~120 output tokens (system prompt +
# retrieved policy text + claim/rental facts -> a 2-3 sentence answer) against Nova Lite's rate
# ($0.06/1M input, $0.24/1M output -- CLAUDE.md's verified environment-facts table, `get_generation_model_id`'s
# flagged default per `config/flags.py`). If `GENERATION_TIER_FLAG` is ever flipped to the alternate
# (Claude Haiku 4.5, $1.00/$5.00 per 1M), this estimate undercounts by roughly 17x -- still negligible
# against the $25 ceiling at this call volume, but stated here rather than silently assumed away.
_GENERATION_CALL_ESTIMATE_USD = 0.0002


def terraform_outputs(stack_dir: Path = STACK_DIR) -> dict[str, Any]:
    result = subprocess.run(
        ["terraform", f"-chdir={stack_dir}", "output", "-json"],
        capture_output=True,
        text=True,
        check=True,
    )
    return {k: v["value"] for k, v in json.loads(result.stdout).items()}


def _event(
    *,
    intent_name: str,
    transcript: str,
    slots: dict[str, Any] | None = None,
    session_attributes: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Same wire shape `tests/unit/test_lex_codehook.py::_event` builds and the real Lex V2 service
    sends -- a fresh `sessionId` per event, so no event's checkpoint state leaks into another's."""
    slots = slots if slots is not None else {}
    return {
        "messageVersion": "1.0",
        "invocationSource": "DialogCodeHook",
        "inputMode": "Speech",
        "responseContentType": "text/plain; charset=utf-8",
        "sessionId": f"verify-lambda-execution-{uuid.uuid4()}",
        "inputTranscript": transcript,
        "bot": {
            "id": "ABCDEFGHIJ",
            "name": "fnol-voice-agent",
            "aliasId": "TSTALIASID",
            "aliasName": "TestBotAlias",
            "localeId": "en_US",
            "version": "DRAFT",
        },
        "interpretations": [
            {
                "intent": {
                    "name": intent_name,
                    "slots": slots,
                    "state": "InProgress",
                    "confirmationState": "None",
                },
                "nluConfidence": 0.98,
            }
        ],
        "sessionState": {
            "sessionAttributes": session_attributes if session_attributes is not None else {},
            "intent": {
                "name": intent_name,
                "slots": slots,
                "state": "InProgress",
                "confirmationState": "None",
            },
            "originatingRequestId": "a1b2c3d4-0000-0000-0000-000000000000",
        },
    }


def _slot(value: str) -> dict[str, Any]:
    return {
        "shape": "Scalar",
        "value": {"originalValue": value, "interpretedValue": value, "resolvedValues": [value]},
    }


def _dialog_action(payload: dict[str, Any]) -> dict[str, Any]:
    session_state = payload.get("sessionState") or {}
    action = session_state.get("dialogAction")
    return action if isinstance(action, dict) else {}


def _session_attributes(payload: dict[str, Any]) -> dict[str, Any]:
    session_state = payload.get("sessionState") or {}
    attributes = session_state.get("sessionAttributes")
    return attributes if isinstance(attributes, dict) else {}


def _message(payload: dict[str, Any]) -> str:
    messages = payload.get("messages") or []
    if messages and isinstance(messages[0], dict):
        return str(messages[0].get("content", ""))
    return ""


def _expect_elicit_slot(slot_name: str) -> Callable[[dict[str, Any]], str | None]:
    def check(payload: dict[str, Any]) -> str | None:
        action = _dialog_action(payload)
        if action.get("type") != "ElicitSlot":
            return f"expected ElicitSlot, got dialogAction={action!r}"
        if action.get("slotToElicit") != slot_name:
            return f"expected slotToElicit={slot_name!r}, got {action.get('slotToElicit')!r}"
        return None

    return check


def _expect_detection_escalation(
    *, must_contain_911: bool
) -> Callable[[dict[str, Any]], str | None]:
    """All three events this is used for (L1, L3, `D79`) are pre-graph paths, so the expected reason is
    specifically `detection-pregraph`, not just any `detection-*` value -- a `detection-graph` reading
    here would mean the pre-graph check DIDN'T fire and the turn fell through to the graph, which is
    itself a real regression on a synthetic event engineered to hit the pre-graph path directly."""

    def check(payload: dict[str, Any]) -> str | None:
        action = _dialog_action(payload)
        if action.get("type") != "Close":
            return f"expected Close, got dialogAction={action!r}"
        attributes = _session_attributes(payload)
        if attributes.get("escalate") != "true":
            return f"expected escalate=true, got sessionAttributes={attributes!r}"
        # `D81` item 4: the deploy gate checks provenance too, not only the raw wire flag -- a
        # fail-closed (or graph-provenance) escalation on one of these deliberately pre-graph synthetic
        # events would itself be a real finding, not a pass.
        if attributes.get("escalation_reason") != "detection-pregraph":
            return (
                f"expected escalation_reason=detection-pregraph, got "
                f"{attributes.get('escalation_reason')!r}"
            )
        message = _message(payload)
        has_911 = "911" in message
        if has_911 != must_contain_911:
            return f"expected 911-in-message={must_contain_911}, got message={message!r}"
        return None

    return check


# `D87` regression events -- real corpus identifiers, `data/synthetic/`. Same values
# `scripts/verify_d87_scope.py` and `scripts/verify_stage_b1_live_invoke.py` used to find and scope the
# defect; reused here rather than invented, so a disagreement in outcome would itself be a signal.
_REAL_CLAIM_NUMBER = "CLM-2608-00042-4"  # policy PY4821, status RepairInProgress
_REAL_POLICY_NUMBER = "PY4821"
# Events 12-13's own real identifiers -- PY4821's OTHER vehicle (not the one CLM-2608-00042-4 is against),
# so `FileAutoClaim`'s write doesn't read as "about" the claim `_REAL_CLAIM_NUMBER` names, even informally.
_REAL_VIN = "9SYAB1239G1000101"  # PY4821, 2022 Example Motors Meridian
_REAL_DRIVER_NAME = (
    "Priya Nakamura"  # PY4821's own policyholder name, data/synthetic/policyholders/
)


def _intent_state(payload: dict[str, Any]) -> str | None:
    session_state = payload.get("sessionState") or {}
    intent = session_state.get("intent")
    return intent.get("state") if isinstance(intent, dict) else None


def _expect_executed_node_intent(payload: dict[str, Any], expected: str) -> str | None:
    """`D90` part 2 (`RESULTS.md` §34/§35, option B). The structural node-identity check events 10-13
    lacked entirely before this fix -- `Close`/`Fulfilled` plus a message-template substring was always an
    inferred, not asserted, proxy for "the intended node produced this" (§34 §2's own finding). Reads the
    ground-truth field `_close()`/`_elicit_slot()` now set from the graph's own `result["intent"]`, never
    from Lex's echoed intent. Deliberately does NOT fall back to a template check on a mismatch -- a
    template match on the wrong node was exactly the false-green risk this field exists to close."""
    attributes = _session_attributes(payload)
    actual = attributes.get("executed_node_intent")
    if actual != expected:
        return (
            f"expected executed_node_intent={expected!r} (the node that should have produced this "
            f"message), got {actual!r}"
        )
    return None


def _expect_claim_status_fulfilled(payload: dict[str, Any]) -> str | None:
    """`D87`. Pre-fix, this event crashes inside `claims_server.py::_load_claims` on `CLAIMS_PATH
    .read_text()` -- the handler's top-level `try/except` swallows it and returns `Delegate` with no
    message (`handler()`'s fail-open path, module docstring). Post-fix, `check_claim_status.py`'s real
    template response reaches `guardrails_output_check` -- which, per `D88` (`RESULTS.md` §33 §2, `OI5`),
    does NOT mask it: the live guardrail config (read directly via `bedrock:GetGuardrail`, not assumed)
    has zero PII entities configured that would ever fire on this domain's own data spoken back to its
    owner. The four identifier regexes that used to trigger `ANONYMIZE` here (including the one that
    matched claim numbers) were deliberately removed at v2->v3, 2026-08-12, Marco-approved, specifically
    because masking a caller's own identifier back to them was assessed a defect with no upside, not a
    protection. **CORRECTED 2026-08-16 (`D88` Option 1, Marco-approved 2026-08-16, applied this entry):**
    this assertion previously expected the claim number ABSENT/masked -- that was this test's own stale
    assumption, not the guardrail's actual, approved, current behavior; the assertion was simply never
    updated when v3 shipped four days before this check was written. Corrected to match v3's real
    behavior: the claim number is expected PRESENT, verbatim, exactly as the events 12/13 checks below
    already (correctly) assert for their own freshly-generated claim numbers.

    `D90` part 2, tightened: the `'...is currently...'` substring used to be this check's only proxy for
    "the CheckClaimStatus node actually produced this" -- replaced with a direct `executed_node_intent`
    read (`RESULTS.md` §35). The substring is kept as a secondary sanity check, not the node-identity
    proof it used to stand in for."""
    action = _dialog_action(payload)
    if action.get("type") != "Close":
        return f"expected Close (real fulfillment), got dialogAction={action!r}"
    if _intent_state(payload) != "Fulfilled":
        return f"expected intent.state=Fulfilled, got {_intent_state(payload)!r}"
    node_error = _expect_executed_node_intent(payload, "CheckClaimStatus")
    if node_error:
        return node_error
    message = _message(payload)
    if "is currently" not in message:
        return f"expected the fulfilled claim-status template ('...is currently...'), got message={message!r}"
    if _REAL_CLAIM_NUMBER not in message:
        return f"expected the real claim number present verbatim (v3's approved, unmasked behavior -- D88), got message={message!r}"
    return None


def _expect_contact_info_updated(payload: dict[str, Any]) -> str | None:
    """`D87`. Pre-fix, this event crashes inside `contact_server.py::_get_store` on `POLICYHOLDERS_PATH
    .read_text()`, reached only after all four slots (including confirm) are filled -- same fail-open
    swallow as above. Post-fix, `update_contact_info_node`'s real success message is
    `f"Done -- your {result.field} is updated."`, with no guardrail-triggering content expected in it.

    `D90` part 2, tightened: `executed_node_intent` replaces the `'Done --'`/`'updated'` substring as the
    node-identity proof; the substring stays as a secondary sanity check (`RESULTS.md` §35)."""
    action = _dialog_action(payload)
    if action.get("type") != "Close":
        return f"expected Close (real fulfillment), got dialogAction={action!r}"
    if _intent_state(payload) != "Fulfilled":
        return f"expected intent.state=Fulfilled, got {_intent_state(payload)!r}"
    node_error = _expect_executed_node_intent(payload, "UpdateContactInfo")
    if node_error:
        return node_error
    message = _message(payload)
    if "Done --" not in message or "updated" not in message:
        return f"expected the real update-confirmation message ('Done -- your ... is updated.'), got message={message!r}"
    if "problem" in message.lower():
        return f"got the error-path message instead of a real update confirmation: {message!r}"
    return None


_CLAIM_NUMBER_RE = re.compile(r"CLM-\d{4}-\d{5}-\d")


def _expect_file_auto_claim_filed(payload: dict[str, Any]) -> str | None:
    """`D87` closure, tightened. Pre-fix, this event crashes inside `claims_server.py::file_new_claim` on
    `POLICYHOLDERS_PATH.read_text()` (via the `payload = json.loads(POLICYHOLDERS_PATH.read_text())` policy
    lookup, before the vehicle lookup even runs) -- same fail-open swallow as events 10-11. Post-fix, the
    node's real success message is `f"Your claim number is {claim.claim_number}. Is there anything else?"`
    -- and per `D88`, the freshly generated claim number is expected PRESENT verbatim (the guardrail's
    claim-number regex was removed at v3, Marco-approved; asserting it absent here would be `D88`'s own
    mistake repeated).

    `D90` part 2, tightened: `executed_node_intent` replaces the `'Your claim number is '` substring as the
    node-identity proof (`RESULTS.md` §35). This is the event `D89` currently blocks -- `guardrails_input_
    check` short-circuits to `graph.py::_guardrail_blocked_response` before `route_and_classify` ever runs,
    so `result["intent"]` is never set on this path and `executed_node_intent` is correctly ABSENT, not
    `"FileAutoClaim"`. That is not a defect in this field: no node with an attributable identity produced
    the blocked-turn message, so absence is the honest value here too, same reasoning as the escalation
    paths (`api/lex_codehook.py`'s own `D90` comment)."""
    action = _dialog_action(payload)
    if action.get("type") != "Close":
        return f"expected Close (real fulfillment), got dialogAction={action!r}"
    if _intent_state(payload) != "Fulfilled":
        return f"expected intent.state=Fulfilled, got {_intent_state(payload)!r}"
    node_error = _expect_executed_node_intent(payload, "FileAutoClaim")
    if node_error:
        return node_error
    message = _message(payload)
    if "Your claim number is " not in message:
        return f"expected the fixed file-claim template ('Your claim number is ...'), got message={message!r}"
    if not _CLAIM_NUMBER_RE.search(message):
        return f"expected a real CLM-YYMM-NNNNN-C claim number in message, got message={message!r}"
    return None


def _expect_rental_towing_fulfilled(payload: dict[str, Any]) -> str | None:
    """`D87` closure, tightened. Pre-fix, this event crashes inside `claims_server.py::get_claim_status`
    on `CLAIMS_PATH.read_text()`, reached once `entitlement_type` is filled -- same fail-open swallow as
    every other `D87` site. Post-fix, `rental_towing_entitlement` makes a REAL Bedrock `Converse` call over
    real retrieved policy text and real claim/rental facts -- the response text is genuinely
    model-generated, not a fixed template, so this check asserts only the structural markers a
    `_paths.py`-shaped crash would flip (module docstring, events 12-13 section), not the generated
    wording.

    `D90` part 2, tightened: this is the event that had NO node-identity check at all before this fix
    (`RESULTS.md` §33/§34's own finding) -- a misroute to any node producing non-empty, non-abstention text
    would have silently passed. `executed_node_intent` now closes that gap. It does not, and cannot, fix
    `D90` part 1: `route_and_classify` still classifies this turn with zero conversational context, and the
    live misroute this event currently reproduces (`ElicitSlot`/`coverage_topic`, i.e. `CoverageQuestion`)
    fails the `Close` check above before this function ever reaches the node-identity check at all -- kept
    here anyway as the check that would have caught the *other* shape of this defect, the one where a
    misroute lands on a real `Close` instead."""
    action = _dialog_action(payload)
    if action.get("type") != "Close":
        return f"expected Close (real fulfillment), got dialogAction={action!r}"
    if _intent_state(payload) != "Fulfilled":
        return f"expected intent.state=Fulfilled, got {_intent_state(payload)!r}"
    node_error = _expect_executed_node_intent(payload, "RentalTowingEntitlement")
    if node_error:
        return node_error
    message = _message(payload)
    if not message.strip():
        return "expected a non-empty generated response, got an empty message"
    if message == "I don't have that in your policy -- let me get you to someone who does.":
        return (
            f"got the node's own RAG-abstention message instead of a generated answer: {message!r}"
        )
    return None


def _expect_fallback_reprompt(payload: dict[str, Any]) -> str | None:
    action = _dialog_action(payload)
    if action.get("type") != "Close":
        return f"expected Close, got dialogAction={action!r}"
    attributes = _session_attributes(payload)
    if "escalate" in attributes:
        return f"expected no escalate attribute on an ordinary no-match, got {attributes!r}"
    message = _message(payload)
    if message != "I didn't quite catch that -- could you say that again?":
        return f"expected the fixed GENERIC_REPROMPT string, got message={message!r}"
    return None


@dataclass
class EventCase:
    name: str
    event: dict[str, Any]
    check: Callable[[dict[str, Any]], str | None]
    reaches_bedrock: bool = field(default=True)
    # Event 13 only: a REAL Bedrock `Converse` generation call (`generate_response`), on top of the
    # guardrail+router calls every `reaches_bedrock=True` event already makes. Tracked separately rather
    # than folded into `_GUARDRAIL_PER_CALL_USD` -- that constant is a guardrail-units rate, not a
    # generation-token rate, and conflating them would be the same silent-staleness shape this file
    # already fixed once for `_ESTIMATED_GUARDRAIL_CALLS` (see the module-level comment above).
    has_generation_call: bool = field(default=False)


def _build_event_matrix() -> list[EventCase]:
    return [
        EventCase(
            "FileAutoClaim first turn",
            _event(intent_name="FileAutoClaim", transcript="I need to file a claim"),
            _expect_elicit_slot("policy_number"),
        ),
        EventCase(
            "CheckClaimStatus first turn",
            _event(intent_name="CheckClaimStatus", transcript="what's the status of my claim"),
            _expect_elicit_slot("claim_or_policy_number"),
        ),
        EventCase(
            "CoverageQuestion first turn",
            _event(intent_name="CoverageQuestion", transcript="am I covered for a rental car"),
            _expect_elicit_slot("coverage_topic"),
        ),
        EventCase(
            "RentalTowingEntitlement first turn",
            _event(
                intent_name="RentalTowingEntitlement",
                transcript="can I get a rental car while mine is being fixed",
            ),
            _expect_elicit_slot("entitlement_type"),
        ),
        EventCase(
            "UpdateContactInfo first turn",
            _event(intent_name="UpdateContactInfo", transcript="I need to update my phone number"),
            _expect_elicit_slot("policy_number"),
        ),
        EventCase(
            "FallbackIntent (unclassifiable turn)",
            _event(intent_name="FallbackIntent", transcript="xyzzy plugh mumble"),
            _expect_fallback_reprompt,
        ),
        EventCase(
            "Raw-text L1 trigger (pre-graph, injury)",
            _event(intent_name="FileAutoClaim", transcript="my passenger isn't moving"),
            _expect_detection_escalation(must_contain_911=True),
            reaches_bedrock=False,
        ),
        EventCase(
            "Raw-text L3 trigger (pre-graph, agent override, D74)",
            _event(intent_name="FileAutoClaim", transcript="agent"),
            _expect_detection_escalation(must_contain_911=False),
            reaches_bedrock=False,
        ),
        EventCase(
            "injuries_present confirmed True, no injury vocabulary (D79)",
            _event(
                intent_name="FileAutoClaim",
                transcript="yes",
                slots={"injuries_present": _slot("Yes")},
            ),
            _expect_detection_escalation(must_contain_911=True),
            reaches_bedrock=False,
        ),
        EventCase(
            "CheckClaimStatus fulfilled, identifier slot pre-filled (D87 regression)",
            _event(
                intent_name="CheckClaimStatus",
                transcript="what's the status of my claim",
                slots={"claim_number": _slot(_REAL_CLAIM_NUMBER)},
            ),
            _expect_claim_status_fulfilled,
        ),
        EventCase(
            "UpdateContactInfo fulfilled, all four slots pre-filled (D87 regression)",
            _event(
                intent_name="UpdateContactInfo",
                transcript="update my phone number",
                slots={
                    "policy_number": _slot(_REAL_POLICY_NUMBER),
                    "field": _slot("phone"),
                    "new_value": _slot("555-0199"),
                    "confirm_update_contact_info": _slot("Yes"),
                },
            ),
            _expect_contact_info_updated,
        ),
        EventCase(
            "FileAutoClaim filed, all slots pre-filled (D87 closure, tightened)",
            _event(
                intent_name="FileAutoClaim",
                transcript="yes, go ahead and file it",
                slots={
                    "policy_number": _slot(_REAL_POLICY_NUMBER),
                    "insured_vehicle_vin": _slot(_REAL_VIN),
                    "loss_datetime": _slot("2026-08-15T14:30:00"),
                    "loss_location": _slot("Highway 401 at Hurontario, Mississauga, ON"),
                    "loss_type": _slot("Collision"),
                    "damage_description": _slot("Rear bumper damage from a rear-end collision"),
                    "other_party_involved": _slot("No"),
                    "police_report_filed": _slot("No"),
                    "driver_name": _slot(_REAL_DRIVER_NAME),
                    "confirm_file_claim": _slot("Yes"),
                },
            ),
            _expect_file_auto_claim_filed,
        ),
        EventCase(
            "RentalTowingEntitlement fulfilled, entitlement+policy pre-filled (D87 closure, tightened)",
            _event(
                intent_name="RentalTowingEntitlement",
                transcript="am I still covered for a rental car",
                slots={
                    "entitlement_type": _slot("rental"),
                    "policy_number": _slot(_REAL_POLICY_NUMBER),
                },
            ),
            _expect_rental_towing_fulfilled,
            has_generation_call=True,
        ),
    ]


def invoke(
    lambda_client: Any, function_name: str, event: dict[str, Any]
) -> tuple[dict[str, Any] | None, str | None]:
    """Returns `(payload, error_detail)`. `error_detail` is set, and `payload` is `None` or best-effort,
    on any of: a transport-level exception, a non-empty `FunctionError`, or a payload that does not parse
    as JSON. Never trusts a bare `StatusCode: 200` -- see the module docstring."""
    try:
        response = lambda_client.invoke(
            FunctionName=function_name,
            InvocationType="RequestResponse",
            Payload=json.dumps(event).encode("utf-8"),
        )
    except Exception as exc:  # noqa: BLE001 - the failure itself is the finding
        return None, f"Invoke raised: {type(exc).__name__}: {exc}"

    raw = response["Payload"].read()
    function_error = response.get("FunctionError")
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        return (
            None,
            f"payload did not parse as JSON ({exc}); FunctionError={function_error!r}; raw={raw[:500]!r}",
        )

    if function_error:
        return payload, f"FunctionError={function_error!r} payload={payload}"

    dialog_type = _dialog_action(payload).get("type")
    if dialog_type not in ("Delegate", "ElicitSlot", "Close"):
        return payload, f"illegal sessionState.dialogAction.type: {dialog_type!r}"

    return payload, None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args(argv)

    matrix = _build_event_matrix()
    if len(matrix) < _MINIMUM_EVENTS:
        print(
            f"=== verify-lambda-execution: event matrix has only {len(matrix)} case(s), "
            f"expected at least {_MINIMUM_EVENTS} -- refusing to report a pass from a shrunk matrix ==="
        )
        return 1

    outputs = terraform_outputs()
    function_name = str(outputs["codehook_function_name"])
    bedrock_events = sum(1 for c in matrix if c.reaches_bedrock)
    generation_events = sum(1 for c in matrix if c.has_generation_call)
    # Derived from the real matrix every run -- see the constant's own comment on why this used to be a
    # hardcoded figure and went stale the moment events 10-11 were added. Generation cost tracked
    # separately from guardrail cost, added 2026-08-16 for event 13 -- see `_GENERATION_CALL_ESTIMATE_USD`.
    estimated_cost_usd = round(
        bedrock_events * _GUARDRAIL_PER_CALL_USD
        + generation_events * _GENERATION_CALL_ESTIMATE_USD,
        6,
    )

    print(f"=== verify-lambda-execution: {function_name}, {len(matrix)} events ===")
    print(
        f"    estimated cost: {bedrock_events} events reach Bedrock (guardrail+router) at roughly "
        f"${_GUARDRAIL_PER_CALL_USD:.6f}/event, plus {generation_events} real generation call(s) at "
        f"roughly ${_GENERATION_CALL_ESTIMATE_USD}/call (unmeasured upper bound) -> ~${estimated_cost_usd} "
        f"total; the other {len(matrix) - bedrock_events} are pre-graph and Bedrock-free. lambda:Invoke "
        f"itself is inside the always-free tier at this volume."
    )
    print(
        f"    NOT a pure liveness check: {bedrock_events} of {len(matrix)} events route through the "
        f"real router+guardrail. A failure there is ambiguous between an infra regression (D80-shaped) "
        f"and an ordinary model-classification miss -- check WHICH event failed before concluding D80 "
        f"recurred."
    )

    lambda_client = boto3.client("lambda", region_name=REGION)
    failures: list[str] = []
    for case in matrix:
        payload, error_detail = invoke(lambda_client, function_name, case.event)
        if error_detail:
            failures.append(f"{case.name}: {error_detail}")
            print(f"  FAIL {case.name}: {error_detail}")
            continue
        assert payload is not None  # invoke() only returns error_detail=None with a real payload
        marker_problem = case.check(payload)
        if marker_problem:
            failures.append(f"{case.name}: {marker_problem}")
            print(f"  FAIL {case.name}: {marker_problem}")
        else:
            print(f"  ok   {case.name}")

    if failures:
        print(f"\n=== verify-lambda-execution FAILED: {len(failures)}/{len(matrix)} event(s) ===")
        return 1

    print(f"\n=== verify-lambda-execution passed: {len(matrix)}/{len(matrix)} events ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

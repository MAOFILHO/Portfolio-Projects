"""Lex V2 codehook — the Lambda entry point Amazon Lex calls on every turn.

Phase 8 Stage 4.

WHAT CHANGED FROM STAGE 3
    `_dispatch()` now invokes the real LangGraph pipeline (`agents/graph.py`), keyed on the Connect
    `contactId` per `ADR-005` -- state (`filled_slots`, `active_slot`, `retry_counts`) persists turn to
    turn via the deployed DynamoDB checkpointer, not via Lex's own session. L1 (raw-text injury lexicon)
    and L3 (`agents/l3_lexicon.py`, the "agent"/"human" override) both run **before** the graph is
    invoked at all, not inside it -- `D74`'s reason: L3 has no representation in the graph whatsoever
    (deliberately, see `bot.yaml.tftpl`'s header comment), and a pre-graph L1 check is what makes the
    fail-open/fail-closed split below possible, since the graph itself might never run long enough to
    report its own L1 verdict if the failure is in reaching AWS at all.

    Response shape (`Delegate`/`ElicitSlot`/`Close`) is now a function of the GRAPH's returned state, not
    of `invocationSource`: `escalation` set -> `Close` with the transfer signalled; `active_slot` set ->
    `ElicitSlot` naming it, with the graph's own message; neither -> `Close`, the intent is done. This is
    a deliberate departure from Stage 3's `invocationSource`-branch, and a more correct one -- Lex calls
    `FulfillmentCodeHook` once it believes every *declared* slot is filled, which does not necessarily
    coincide with the moment the GRAPH considers the conversation done (the confirm-then-file step, see
    `D78` below, runs entirely inside a nominal `DialogCodeHook`/`FulfillmentCodeHook` turn either way).
    `tests/unit/test_lex_codehook.py` was updated to match, documented there rather than silently.

`D78` -- THE LEX BOT AND THE GRAPH HAD NEVER BEEN CONNECTED, AND THEIR VOCABULARIES HAD DRIFTED
    Found wiring this module to the real graph for the first time -- the same shape as every Stage 3
    defect (`RESULTS.md` §3.5 family): two components each individually tested and each individually
    correct, never run against each other for real. `bot.yaml.tftpl`'s declared slot names had drifted
    from the `filled_slots` keys `agents/nodes/*.py` have used since Phase 5:

      * FileAutoClaim: `insured_vehicle` -> renamed to `insured_vehicle_vin`.
      * UpdateContactInfo: `contact_field`/`contact_new_value` -> renamed to `field`/`new_value`; a
        `policy_number` slot was missing entirely (the write's own authentication field) and was added.
      * RentalTowingEntitlement: `entitlement_claim_number` -> renamed to `claim_number`; `entitlement_type`
        (`rental_towing.py`'s own first branch) had no Lex slot at all and was added, with a new
        `EntitlementTypeValues` custom slot type.
      * Both write-path/file-path confirmation steps (`file_auto_claim.py`'s `confirm_file_claim`,
        `update_contact_info.py`'s `confirm_update_contact_info`) are pure graph/codehook state with no
        Lex slot behind them at all -- declared now, as `AMAZON.Confirmation` slots, purely so
        `ElicitSlot` has a legal target; their `PromptSpecification` is never what a caller actually
        hears, the graph's own dynamic summary/read-back always is.

    Every rename and addition is in `bot.yaml.tftpl`, each comment-tagged `D78` at its exact location.
    Verified against a real `templatefile()` render, not just read: every intent's `SlotPriorities` set
    equals its declared `Slots` set, and every graph node's own slot-key literals now match the Lex
    declaration verbatim -- both checked mechanically, not by inspection alone (see the Stage 4 session
    notes for the exact verification).

`D79` -- `injuries_present` CONFIRMED TRUE HAS NO PATH TO L1
    L1 (`agents/lexicon.py`) is a pure function of **raw turn text**. `injuries_present` is Lex's own
    first-priority `AMAZON.Confirmation` slot -- "Is anyone hurt, including you?" -- and a caller who
    answers it with the single word "yes" produces raw text L1's lexicon was never going to match; "yes"
    contains no injury vocabulary. `bot.yaml.tftpl`'s own comment on this slot ("any affirmative
    escalates immediately... a confirm step would be a negotiation") already stated the requirement; there
    was no code that met it. This module closes it as its own explicit check, structurally parallel to L1
    and L3 rather than folded into either: `filled_slots["injuries_present"] is True`, evaluated on the
    MERGED slot state (this turn's answer plus everything the checkpointer already had), triggers the
    identical L1-shaped escalation this module builds for a raw-text L1 match.

`ADR-009`
    No client at module load, no import of `boto3` at module scope -- every AWS-touching import is local
    to `_build_graph()`, called at most once per warm Lambda instance and cached in `_GRAPH`.
    `tests/unit/test_lex_codehook.py` asserts both the source-level and the observed (`sys.modules`) form
    of this; a real graph is injected into tests via `_get_graph`, never constructed for real in this
    suite.

FAIL-OPEN / FAIL-CLOSED, SPLIT (Stage 4 owns what Stage 3's docstring flagged as unexamined)
    A pre-graph L1/L3/`injuries_present` check runs BEFORE the graph is ever invoked, purely so this
    split has something to consult if the graph invocation itself raises. No safety signal detected on
    this turn -> fail OPEN (`Delegate`), same posture as Stage 3, for the same reason: an unhandled
    exception on an ordinary turn is dead air, and handing control back to Lex's own state machine is
    better than that. A safety signal WAS detected on this turn -> fail CLOSED (a deterministic
    escalation `Close`, built without the graph, from the pre-graph check alone): once L1/L3/
    `injuries_present` has fired, proceeding as if it hadn't is exactly the `C1` breach wearing a
    resilience argument the Stage 3 docstring named and declined to fix on the spot.

`D81` ITEM 4 -- `escalation_reason` IS NOW A FIRST-CLASS `sessionAttributes` FIELD
    `PROJECT_STATE.md`'s `D81` entry, on review: `escalate="true"` alone cannot distinguish a genuine
    detection from the fail-closed default above, both of which set it identically. `_close()` now takes
    a required `escalation_reason` whenever `escalated=True` -- there is no default, a caller that omits
    it raises, because an unattributed escalation is exactly the silent case this fix exists to remove --
    and writes it into `sessionAttributes["escalation_reason"]`, readable directly from the
    `RecognizeText`/`lambda:Invoke` response with no CloudWatch correlation needed.

    **Split further on review, 2026-08-13: `"detection"` alone was the same defect one level down.**
    The pre-graph L1/L3 raw-text checks and `D79`'s confirmed-slot check are a structurally different
    path from the graph's own in-band `L1`/`L2` branch in `_respond_from_graph_result` -- one runs before
    the graph is ever invoked and cannot depend on it being reachable at all, the other runs only because
    the graph WAS reachable and classified the turn itself. Tagging both `"detection"` produced identical
    text for genuinely different paths, the exact shape `D81` itself was written to fix one level up (the
    original `"escalating contact %s on layer %s route %s"` log line, identical for a genuine `L1` hit
    and an `L1`-shaped fail-closed default). Four values now: `"detection-pregraph"` (the raw-text L1/L3
    checks and `D79`'s slot check, all in `_dispatch` -- bypass the graph and the checkpointer's turn
    invocation entirely, or in `D79`'s case read the checkpointer but never invoke the graph);
    `"detection-graph"` (the graph's own in-band `L1`/`L2` branch in `_respond_from_graph_result` --
    requires the graph to have run to completion); `"fail-closed"` for the one path where nothing was
    detected except that the graph could not be reached; `"other-default"` reserved for the harness's own
    defensive classification of a shape this module never actually emits. **Both `detection-*` values
    are genuine detections and both count toward `C1` recall** -- the split exists so a provenance
    breakdown can show WHICH fired, not to demote one relative to the other.
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any, Literal

from fnol_voice_agent.agents.l3_lexicon import detect_agent_override
from fnol_voice_agent.agents.lexicon import detect_safety_trigger
from fnol_voice_agent.mcp.escalation_server import initiate_escalation

logger = logging.getLogger(__name__)

# `D81` item 4, split by path on review -- `"detection-pregraph"` and `"detection-graph"` are BOTH
# genuine detections (both count toward C1 recall); the split exists so provenance shows which of two
# structurally different paths fired, not to rank one above the other. `"other-default"` is never written
# by this module -- it names the residual bucket the HARNESS falls back to if it ever observes
# `escalate=true` with a missing or unrecognized reason, so that shape has a name to be counted under
# rather than being silently folded into a detection value (which would flatter a broken emitter) or
# "fail-closed" (which would blame this module for a shape it never actually produced).
EscalationReason = Literal["detection-pregraph", "detection-graph", "fail-closed", "other-default"]

# DIALOGUE-POLICIES.md §5 step 1, verbatim -- the same fixed script injury_escalation.py speaks when the
# graph itself catches the trigger. Spoken here too so a caller hears the identical line regardless of
# which of the three paths (graph L1, pre-graph L1, injuries_present) caught it.
_SAFETY_SCRIPT = (
    "If anyone needs medical help, please hang up and call 911. "
    "I'm connecting you with someone who can help right away."
)
# DIALOGUE-POLICIES.md §8, route 2.
_AGENT_OVERRIDE_SCRIPT = "Sure -- connecting you with someone now."
# Fail-closed, L1 path: system trouble on a turn that already carried an injury disclosure. The 911 line
# is non-negotiable regardless of why the graph could not be reached -- omitting it here to keep the
# message "about the outage" would be choosing the wrong thing to be honest about.
_UNAVAILABLE_SAFETY_SCRIPT = (
    "If anyone needs medical help, please hang up and call 911. "
    "I'm having trouble with our system right now, so let me connect you with someone directly."
)
# Fail-closed, L3 path: the caller asked for a human and the graph could not be reached to hand them off
# normally. Deliberately does NOT reuse `_UNAVAILABLE_SAFETY_SCRIPT` -- a caller who never mentioned
# injury should not hear the 911 line, which is exactly the bug `tests/unit/test_lex_codehook.py::test_
# a_raw_text_l3_match_escalates_even_when_the_graph_cannot_be_reached` was written to catch and did.
_UNAVAILABLE_OVERRIDE_SCRIPT = (
    "I'm having trouble with our system right now, so let me connect you with someone directly."
)

_GRAPH: Any = None  # lazily built and cached per warm instance -- ADR-009. See `_get_graph`.


def _build_graph() -> Any:
    """Real dependencies. Every AWS-touching import is local to this function, not module-level -- the
    thing `test_the_module_imports_without_botocore_being_loaded` checks for."""
    from fnol_voice_agent.agents.graph import build_graph
    from fnol_voice_agent.aws.bedrock_router import get_bedrock_runtime_client
    from fnol_voice_agent.aws.checkpointer import build_checkpointer
    from fnol_voice_agent.config.settings import DEFAULT_REGION
    from fnol_voice_agent.guardrails.client import BedrockGuardrailClient
    from fnol_voice_agent.knowledge.ingest import BedrockEmbedder, DynamoVectorStore

    checkpointer = build_checkpointer(os.environ["FNOL_CHECKPOINT_TABLE"], region=DEFAULT_REGION)
    vector_store = DynamoVectorStore(
        table_name=os.environ["FNOL_VECTOR_TABLE"], region=DEFAULT_REGION
    )
    embedder = BedrockEmbedder(region=DEFAULT_REGION)
    bedrock_caller = get_bedrock_runtime_client(region=DEFAULT_REGION)

    # `BedrockGuardrailClient` raises at construction on a blank id/version (by design -- see its own
    # docstring), so an unconfigured guardrail must resolve to `None` (MockGuardrailClient inside
    # build_graph) rather than reach that constructor at all.
    guardrail_id = os.environ.get("FNOL_GUARDRAIL_ID", "")
    guardrail_version = os.environ.get("FNOL_GUARDRAIL_VERSION", "")
    guardrail_client = (
        BedrockGuardrailClient(guardrail_id, guardrail_version, region=DEFAULT_REGION)
        if guardrail_id and guardrail_version
        else None
    )

    return build_graph(
        vector_store=vector_store,
        embedder=embedder,
        bedrock_caller=bedrock_caller,
        guardrail_client=guardrail_client,
        checkpointer=checkpointer,
    )


def _get_graph() -> Any:
    """The one seam Stage 4's tests patch. Production never overrides this; tests replace it with a
    locally-built graph (fake Bedrock caller, mock guardrail, in-memory/moto checkpointer) so the real
    dispatch logic below is exercised deterministically and with zero AWS, per `CLAUDE.md`."""
    global _GRAPH
    if _GRAPH is None:
        _GRAPH = _build_graph()
    return _GRAPH


# ---------------------------------------------------------------------------------------------------
# Wire-contract helpers -- unchanged from Stage 3 in shape, reused rather than re-derived.
# ---------------------------------------------------------------------------------------------------


def _intent_from(event: dict[str, Any]) -> dict[str, Any]:
    """The intent to echo back, taken from `sessionState` and never rebuilt.

    Rebuilding it is how slot values get dropped: an intent returned without its `slots` map erases every
    value collected so far, and the caller experiences that as being asked the same question again. Lex
    reports no error for it. So the whole object round-trips and the handler mutates only what it means
    to change.
    """
    session_state = event.get("sessionState") or {}
    intent = session_state.get("intent")

    if isinstance(intent, dict):
        return dict(intent)

    interpretations = event.get("interpretations") or []
    if interpretations and isinstance(interpretations[0], dict):
        candidate = interpretations[0].get("intent")
        if isinstance(candidate, dict):
            return dict(candidate)

    return {"name": "FallbackIntent", "slots": {}, "state": "InProgress"}


def _session_attributes_from(event: dict[str, Any]) -> dict[str, str]:
    """Session attributes round-trip untouched. `ADR-005` keys the checkpointer on the Connect
    `contactId`, which reaches Lex as a session attribute set by the contact flow."""
    session_state = event.get("sessionState") or {}
    attributes = session_state.get("sessionAttributes")
    return dict(attributes) if isinstance(attributes, dict) else {}


def _contact_id_from(event: dict[str, Any]) -> str:
    """`ADR-005`'s `thread_id`. Falls back to Lex's own `sessionId` rather than a constant -- a missing
    `contactId` should key a wrong-but-distinct conversation, never silently merge every misconfigured
    call into one shared thread."""
    contact_id = _session_attributes_from(event).get("contactId")
    if contact_id:
        return contact_id
    session_id = event.get("sessionId")
    return str(session_id) if session_id else "unknown"


def _turn_input_from(event: dict[str, Any]) -> str:
    transcript = event.get("inputTranscript")
    return str(transcript) if transcript else ""


def _delegate(event: dict[str, Any]) -> dict[str, Any]:
    """Hand the turn back to Lex's own elicitation state machine. Fail-OPEN response shape."""
    return {
        "sessionState": {
            "dialogAction": {"type": "Delegate"},
            "intent": _intent_from(event),
            "sessionAttributes": _session_attributes_from(event),
        }
    }


def _close(
    event: dict[str, Any],
    message: str,
    *,
    escalated: bool = False,
    escalation_reason: EscalationReason | None = None,
) -> dict[str, Any]:
    intent = _intent_from(event)
    intent["state"] = "Fulfilled"

    session_attributes = _session_attributes_from(event)
    if escalated:
        if escalation_reason is None:
            # `D81` item 4: every escalation this module produces must be attributable. This is not a
            # defensive fallback to a default value -- a caller reaching this line without naming why
            # is a bug in THIS module, and the fix for `D81` is exactly to stop letting that happen
            # silently the way `escalate="true"` alone always did.
            raise ValueError("_close(escalated=True) requires an explicit escalation_reason")
        # `D43`/`NOT-FIXED.md` #2: the signal the contact flow's own Check-Attributes branch acts on to
        # perform the real Connect transfer. Set here, at the one boundary that knows whether this
        # response is actually going to reach a live Connect flow -- not asserted by the graph, which has
        # no notion of Connect at all.
        session_attributes["escalate"] = "true"
        # `D81` item 4: readable directly from the wire response, no CloudWatch correlation needed.
        session_attributes["escalation_reason"] = escalation_reason

    return {
        "sessionState": {
            "dialogAction": {"type": "Close"},
            "intent": intent,
            "sessionAttributes": session_attributes,
        },
        "messages": [{"contentType": "PlainText", "content": message}],
    }


def _elicit_slot(event: dict[str, Any], slot_name: str, message: str) -> dict[str, Any]:
    """`ElicitSlot`, targeting whatever slot the GRAPH decided to ask about next -- never Lex's own
    `SlotPriorities` walk, which is why `D78`'s renames made every `active_slot` the graph can produce a
    legal Lex slot name rather than something this function has to translate."""
    return {
        "sessionState": {
            "dialogAction": {"type": "ElicitSlot", "slotToElicit": slot_name},
            "intent": _intent_from(event),
            "sessionAttributes": _session_attributes_from(event),
        },
        "messages": [{"contentType": "PlainText", "content": message}],
    }


# ---------------------------------------------------------------------------------------------------
# Slot-value translation -- Lex's wire shape into the graph's `filled_slots`.
# ---------------------------------------------------------------------------------------------------


def _coerce_slot_value(value: Any) -> Any:
    """Lex's `AMAZON.Confirmation` slots resolve to the literal strings `"Yes"`/`"No"`, and every graph
    node that reads a confirmation slot compares against the Python singleton `True`
    (`filled[_CONFIRM_KEY] is not True`) -- an uncoerced `"Yes"` fails that check exactly like `"No"`
    does, which is a silent, opposite-of-intended bug, not a loud one. No other slot type in this bot ever
    resolves to exactly `"Yes"`/`"No"`, so this coercion is safe applied blind, without needing a
    per-slot-name table that could drift from `bot.yaml.tftpl` the way `D78`'s renames just did.
    """
    if value == "Yes":
        return True
    if value == "No":
        return False
    return value


def _lex_interpreted_slots(event: dict[str, Any]) -> dict[str, Any]:
    session_state = event.get("sessionState") or {}
    intent = session_state.get("intent") or {}
    slots = intent.get("slots") or {}

    interpreted: dict[str, Any] = {}
    for name, slot in slots.items():
        if not isinstance(slot, dict):
            continue
        value = slot.get("value")
        if not isinstance(value, dict):
            continue
        raw = value.get("interpretedValue")
        if raw is not None:
            interpreted[name] = _coerce_slot_value(raw)
    return interpreted


def _merged_filled_slots(previous: dict[str, Any], event: dict[str, Any]) -> dict[str, Any]:
    """Previously-checkpointed `filled_slots`, with whatever Lex has interpreted for THIS intent's slots
    merged on top. Lex keeps every slot it has ever filled for the current intent in `sessionState.intent.
    slots` turn over turn, so this re-merges already-known values every turn -- harmless (idempotent) and
    simpler than tracking only "this turn's new answer," which would have to special-case the confirm
    slots (`D78`) that Lex's own dialog manager does not walk toward on its own.
    """
    merged = dict(previous)
    merged.update(_lex_interpreted_slots(event))
    return merged


# ---------------------------------------------------------------------------------------------------
# Escalation construction -- shared by the graph's own result, the pre-graph L3 check, the
# `injuries_present` check (`D79`), and the fail-closed path.
# ---------------------------------------------------------------------------------------------------


def _escalate(
    event: dict[str, Any],
    *,
    contact_id: str,
    triggering_layer: str,
    route: int,
    message: str,
    context: dict[str, Any],
    escalation_reason: EscalationReason,
) -> dict[str, Any]:
    result = initiate_escalation(
        contact_id=contact_id, triggering_layer=triggering_layer, context=context
    )
    # `D81` item 4: `reason` added to the log line itself, not only to `sessionAttributes` -- the two
    # channels answer different questions (the wire response is what the harness reads per-call; the log
    # line is what a CloudWatch query over a whole window can group by) and before this fix neither one
    # actually carried it.
    logger.info(
        "escalating contact %s on layer %s route %s reason %s",
        contact_id,
        result.triggering_layer,
        route,
        escalation_reason,
    )
    return _close(event, message, escalated=True, escalation_reason=escalation_reason)


# ---------------------------------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------------------------------


def _run_graph_turn(
    contact_id: str,
    turn_input: str,
    filled_slots: dict[str, Any],
    previous: dict[str, Any],
) -> dict[str, Any]:
    """`filled_slots`/`previous` are supplied by the caller rather than re-read here -- `_dispatch` already
    fetched them (checkpointer state is needed before this point regardless, for `D79`'s check), and a
    second `graph.get_state()` call would be a second DynamoDB read on every ordinary turn for no reason.
    """
    graph = _get_graph()
    config = {"configurable": {"thread_id": contact_id}}

    result: dict[str, Any] = graph.invoke(
        {
            "contact_id": contact_id,
            "turn_input": turn_input,
            "filled_slots": filled_slots,
            "active_slot": previous.get("active_slot"),
            "retry_counts": previous.get("retry_counts", {}),
            # No barge-in signal reaches this handler yet -- `DIALOGUE-POLICIES.md` §6 designed the
            # ordering; wiring the actual Connect/Lex signal that flips this is unscheduled and named
            # here rather than assumed, same shape as `AI-USE-CASE-CARD.md` F8.
            "is_barge_in": False,
        },
        config,
    )
    return result


def _respond_from_graph_result(event: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    response_text = result.get("response_text") or (
        "I'm sorry, something went wrong on my end. Let me connect you with someone who can help."
    )

    escalation = result.get("escalation")
    if escalation:
        # `D81` item 4(b): this branch used to call `_close(..., escalated=True)` directly, with no
        # logging and no provenance signal at all -- the least observable of the three escalation paths,
        # not a baseline the other two merely fell short of. `injury_escalation()` (`agents/nodes/
        # injury_escalation.py`) already called `initiate_escalation()` itself and returned the resulting
        # `EscalationRecord` as `result["escalation"]`; logging it here is making an already-computed
        # record observable through the same channel every other path uses, not a second escalation call
        # -- calling `initiate_escalation()` again here would double-count it.
        logger.info(
            "escalating contact %s on layer %s route %s reason %s",
            escalation.get("contact_id"),
            escalation.get("triggering_layer"),
            escalation.get("route"),
            "detection-graph",
        )
        return _close(event, response_text, escalated=True, escalation_reason="detection-graph")

    active_slot = result.get("active_slot")
    if active_slot:
        return _elicit_slot(event, active_slot, response_text)

    return _close(event, response_text)


def _dispatch(event: dict[str, Any]) -> dict[str, Any]:
    contact_id = _contact_id_from(event)
    turn_input = _turn_input_from(event)

    l3_fired, l3_term = detect_agent_override(turn_input)
    l1_fired, l1_term = detect_safety_trigger(turn_input)

    if l1_fired:
        # Bypass the graph and the checkpointer entirely -- no model call, no dependency on anything
        # that can fail, cheapest and fastest path to the one response that matters. This is the actual
        # AWS-independent property the module docstring claims for L1; routing this through
        # `graph.get_state()` first (an earlier version of this function did) would have made that claim
        # false for every raw-text match, not just the ones the checkpointer happens to be reachable for.
        return _escalate(
            event,
            contact_id=contact_id,
            triggering_layer="L1",
            route=1,
            message=_SAFETY_SCRIPT,
            context={"triggering_utterance": turn_input, "matched_term": l1_term},
            escalation_reason="detection-pregraph",
        )

    # `D79`. Raw text alone didn't catch it -- the only way to know whether `injuries_present` was
    # confirmed (this turn or a prior one) is to read the checkpointer, so this is the first point in an
    # ordinary turn that touches AWS at all.
    #
    # `D83` TEMPORARY diagnostic logging (Marco-approved 2026-08-13) -- localizes a hang to graph
    # construction vs. the first checkpointer read. Remove once D83 is diagnosed, same revert as the
    # 60s timeout in `variables.tf`.
    _d83_t0 = time.monotonic()
    logging.getLogger(__name__).info("D83 diag: calling _get_graph() at t=0.000s")
    graph = _get_graph()
    logging.getLogger(__name__).info(
        "D83 diag: _get_graph() returned after %.3fs", time.monotonic() - _d83_t0
    )
    config = {"configurable": {"thread_id": contact_id}}
    logging.getLogger(__name__).info(
        "D83 diag: calling graph.get_state() at t=%.3fs", time.monotonic() - _d83_t0
    )
    state_snapshot = graph.get_state(config)
    logging.getLogger(__name__).info(
        "D83 diag: graph.get_state() returned after %.3fs", time.monotonic() - _d83_t0
    )
    previous = state_snapshot.values or {}
    filled_slots = _merged_filled_slots(previous.get("filled_slots", {}), event)

    if filled_slots.get("injuries_present") is True:
        # Same script, same layer, same route as a raw-text L1 match -- DIALOGUE-POLICIES.md §5 step 1
        # does not distinguish how the disclosure arrived, and neither does this response.
        return _escalate(
            event,
            contact_id=contact_id,
            triggering_layer="L1",
            route=1,
            message=_SAFETY_SCRIPT,
            context={
                "filled_slots": filled_slots,
                "triggering_utterance": turn_input,
                "slot_confirmed": True,
            },
            escalation_reason="detection-pregraph",
        )

    if l3_fired:
        return _escalate(
            event,
            contact_id=contact_id,
            triggering_layer="L3",
            route=2,
            message=_AGENT_OVERRIDE_SCRIPT,
            context={
                "filled_slots": filled_slots,
                "triggering_utterance": turn_input,
                "matched_term": l3_term,
            },
            escalation_reason="detection-pregraph",
        )

    result = _run_graph_turn(contact_id, turn_input, filled_slots, previous)
    return _respond_from_graph_result(event, result)


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Lambda entry point. `fnol_voice_agent.api.lex_codehook.handler`."""
    if not isinstance(event, dict):
        return _delegate({})

    turn_input = _turn_input_from(event)
    # Pre-graph, AWS-independent signal -- computed BEFORE the try/except so it is available to decide
    # fail-open vs fail-closed even if everything downstream (the graph, the checkpointer, Bedrock) is
    # unreachable. `D79`'s slot-level signal is deliberately NOT included here: reading it requires the
    # checkpointer (`graph.get_state`), which is exactly the call most likely to be the thing that failed
    # -- if it did, a raw-text check is the only signal this handler can still trust.
    l1_fired, _ = detect_safety_trigger(turn_input)
    l3_fired, l3_term = detect_agent_override(turn_input)
    safety_signal_present = l1_fired or l3_fired

    try:
        return _dispatch(event)
    except Exception:  # noqa: BLE001 - see the module docstring on the fail-open/fail-closed split
        logger.exception("codehook failed")
        if not safety_signal_present:
            return _delegate(event)

        contact_id = _contact_id_from(event)
        message = _UNAVAILABLE_SAFETY_SCRIPT if l1_fired else _UNAVAILABLE_OVERRIDE_SCRIPT
        return _escalate(
            event,
            contact_id=contact_id,
            triggering_layer="L1" if l1_fired else "L3",
            route=1 if l1_fired else 2,
            message=message,
            context={
                "triggering_utterance": turn_input,
                "matched_term": l3_term if l3_fired and not l1_fired else None,
                "reason": "graph_invocation_failed",
            },
            escalation_reason="fail-closed",
        )

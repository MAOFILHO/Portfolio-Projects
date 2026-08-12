"""`CoverageQuestion` -- the compound decision path from `DIALOGUE-POLICIES.md` §2. `coverage_question_type`
arrives already classified in `state` (the merged router+L2 call, `routing.py`) -- this node does not
re-classify, it branches on what routing already decided.

No sensible default exists for `store`/`embedder` in Phase 5 -- no real DynamoDB table is provisioned
(`docs/phase5/BUILD-PLAN.md` §2), so unlike the guardrails node's `MockGuardrailClient` default, silently
defaulting knowledge retrieval to an empty store would return "nothing found" for every real query once
Phase 8 exists, which is a worse failure than requiring the caller to supply one. `make_coverage_question_node`
therefore requires both explicitly.
"""

from __future__ import annotations

from typing import Any

from fnol_voice_agent.agents.authority import ELIGIBILITY_DEFLECTION
from fnol_voice_agent.agents.state import AgentState, NodeFn
from fnol_voice_agent.aws.bedrock_router import BedrockConverseCaller, generate_response
from fnol_voice_agent.knowledge.ingest import DynamoVectorStore, Embedder
from fnol_voice_agent.knowledge.retrieve import search
from fnol_voice_agent.mcp.policy_server import PolicyNotFoundError, get_policyholder_elections

_MISSING_TOPIC_PROMPT = "What's your coverage question about?"
_TOPIC_SLOT = "coverage_topic"
_ABSTENTION = "I don't have that in your policy -- let me get you to someone who does."

# DIALOGUE-POLICIES.md §2 step 4: fixed, never generated -- an eligibility/amount question is deflected
# before generation is ever invoked, not answered and then checked.
#
# The string itself now lives in `agents/authority.py`, because Phase 7 added a second enforcement point
# for this same policy on the output side (`ADR-015`) and two enforcement points speaking two different
# sentences would be a defect a caller could hear. This branch is still the primary one -- routing-time
# deflection is what "escalate-before-generate" means, and the output check is a backstop for the case
# where the router had no reason to deflect because the caller's question was benign.
_ELIGIBILITY_DEFLECTION = ELIGIBILITY_DEFLECTION

# PROMPT-REGISTRY.md §3.1, verbatim.
_COVERAGE_SYSTEM_PROMPT = (
    "Answer the caller's coverage question using only the policy text and, if provided, their specific "
    "election record below. State the answer first, in one sentence. You may add one short supporting "
    "clause from the retrieved text if it adds real information (a limit, a condition) -- otherwise stop "
    "after the first sentence. Never exceed two sentences. Do not restate the caller's question. Do not "
    'add a disclaimer, caveat, or "please note" unless the policy text itself states a condition the '
    "caller needs to know. If the retrieved text does not clearly answer the question, say exactly: "
    '"I don\'t have that in your policy -- let me get you to someone who does." Never guess.'
)


def make_coverage_question_node(
    *,
    store: DynamoVectorStore,
    embedder: Embedder,
    bedrock_caller: BedrockConverseCaller | None = None,
) -> NodeFn:
    def coverage_question(state: AgentState) -> dict[str, Any]:
        filled = state.get("filled_slots", {})
        policy_number = filled.get("policy_number")
        coverage_topic = filled.get(_TOPIC_SLOT)

        if not coverage_topic:
            if state.get("active_slot") == _TOPIC_SLOT:
                return {"active_slot": _TOPIC_SLOT, "response_text": None}
            return {"active_slot": _TOPIC_SLOT, "response_text": _MISSING_TOPIC_PROMPT}

        question_type = state.get("coverage_question_type", "not_applicable")

        # DIALOGUE-POLICIES.md §2 step 4 -- deflect before any retrieval or generation is attempted.
        if question_type == "eligibility_amount":
            return {"active_slot": None, "response_text": _ELIGIBILITY_DEFLECTION}

        results = search(coverage_topic, store, embedder, top_k=3)
        if not results:
            return {"active_slot": None, "response_text": _ABSTENTION}
        retrieved_text = "\n".join(r.text for r in results)

        context_parts = [f"Retrieved policy text:\n{retrieved_text}"]
        if question_type == "election_fact_optional" and policy_number:
            try:
                policyholder = get_policyholder_elections(policy_number)
            except PolicyNotFoundError:
                policyholder = None
            if policyholder is not None:
                context_parts.append(
                    f"Policyholder election record (policy {policy_number}): "
                    f"{policyholder.accident_benefits_elections.model_dump()}"
                )

        context_parts.append(f'Caller\'s question: "{coverage_topic}"')
        user_message = "\n\n".join(context_parts)

        answer = generate_response(_COVERAGE_SYSTEM_PROMPT, user_message, caller=bedrock_caller)
        return {"active_slot": None, "response_text": answer}

    return coverage_question

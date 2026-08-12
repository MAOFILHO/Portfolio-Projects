"""Escalation domain -- `InitiateEscalation` (`docs/phase4/DIALOGUE-POLICIES.md` §5/§8;
`docs/phase5/BUILD-PLAN.md` Stage 2).

Same ADR-012 shape as `policy_server.py`: everything above `main()` is plain, transport-agnostic
Python; nothing above `main()` imports the `mcp` package. See `policy_server.py`'s module docstring
for the full rationale.

**This is a stub, and says so in its own return value.** Real Amazon Connect transfer wiring (an
actual queue transfer, an actual contact-flow branch) is Phase 8's job, per
`docs/phase5/BUILD-PLAN.md` Stage 2's explicit scope note -- this handler is not built to look like
that job is already done. It validates its arguments and returns a structured handoff record;
`real_connect_transfer_executed` is always `False`, not omitted, so nothing downstream can mistake this
for a real transfer by absence of a field.
"""

from __future__ import annotations

from typing import Any, Literal, cast

from pydantic import BaseModel, Field, ValidationError

# DIALOGUE-POLICIES.md §8's full escalation-trigger table, not just the three safety-detection layers:
# L1 (deterministic injury/fatality pre-node), L2 (merged router's recall-biased safety classification),
# L3 (hard "agent"/"human" barge-in intent) are routes 1-2; "capability" (out-of-corpus, out-of-scope,
# unresolved ambiguity, retry-ceiling exhaustion) is route 3; "confidence" (sustained low ASR/intent
# confidence, a groundedness self-check failure) is route 4. Stage 6 found this module's original
# Literal only listed L1/L2/L3 even though this very docstring already said "plus the capability/
# confidence routes in §8" -- the type just hadn't been updated to match. Fixed here, not routed around
# by mislabeling a capability escalation as L3 (which specifically means "the caller explicitly asked
# for a human" -- a system-initiated capability escalation is a different fact and must not be recorded
# as if the caller had asked).
TriggeringLayer = Literal["L1", "L2", "L3", "capability", "confidence"]


class InvalidEscalationRequestError(ValueError):
    """Raised when `contact_id` is blank or `triggering_layer` isn't one of L1/L2/L3/capability/
    confidence. Closes `docs/phase2/THREAT-MODEL.md`'s "MCP argument validation not yet built" residual
    risk for this tool.
    """


class InitiateEscalationArgs(BaseModel):
    """Input schema for `initiate_escalation` -- defined once, imported by nothing else (one adapter
    pair per tool)."""

    contact_id: str = Field(min_length=1)
    triggering_layer: TriggeringLayer
    context: dict[str, Any] = Field(default_factory=dict)


class EscalationResult(BaseModel):
    """Output schema -- defined once, returned unchanged by both adapters. Deliberately carries no
    generated ID, timestamp, or other non-deterministic content: this handler's whole output is a pure
    function of its input, which is also what makes `tests/unit/test_mcp_wire_protocol.py`'s
    call-it-both-ways equality assertion meaningful for this tool.
    """

    contact_id: str
    triggering_layer: TriggeringLayer
    status: Literal["transfer_initiated"] = "transfer_initiated"
    context: dict[str, Any]
    real_connect_transfer_executed: Literal[False] = False


def initiate_escalation(
    contact_id: str, triggering_layer: str, context: dict[str, Any] | None = None
) -> EscalationResult:
    """Returns a structured "transfer initiated" handoff record: which contact, which detection layer
    fired, and the full captured context (`DIALOGUE-POLICIES.md` §5 step 3 -- whatever slots were
    already filled, plus the triggering utterance verbatim) the human agent should see. Does not perform
    any real Amazon Connect transfer (Phase 8's scope, not this one's).

    Raises:
        InvalidEscalationRequestError: `contact_id` is blank, or `triggering_layer` isn't L1/L2/L3.
    """
    try:
        # `triggering_layer` is deliberately typed `str` on this function's own signature -- a caller
        # (or the MCP client) may pass anything, and it's `InitiateEscalationArgs`' job to reject a
        # value outside L1/L2/L3 at runtime. The `cast` only tells mypy that; pydantic still validates
        # the actual value against the `Literal` regardless of what the cast claims.
        args = InitiateEscalationArgs(
            contact_id=contact_id,
            triggering_layer=cast(TriggeringLayer, triggering_layer),
            context=context or {},
        )
    except ValidationError as exc:
        raise InvalidEscalationRequestError(str(exc)) from exc

    return EscalationResult(
        contact_id=args.contact_id,
        triggering_layer=args.triggering_layer,
        context=args.context,
    )


def main() -> None:
    """MCP-server adapter: registers `initiate_escalation` as a tool and serves it over stdio."""
    from mcp.server.mcpserver import MCPServer  # local import -- see policy_server.py's docstring

    server = MCPServer("fnol-escalation-server", instructions=__doc__)
    server.add_tool(initiate_escalation)
    server.run()


if __name__ == "__main__":
    main()

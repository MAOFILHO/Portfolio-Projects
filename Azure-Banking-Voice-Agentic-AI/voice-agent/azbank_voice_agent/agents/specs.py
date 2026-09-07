"""The declarative agent table (issue #20): identity, instructions, tool scope -- data, not code.

Phase 1 and Phase 2.1-2.3 had exactly one agent and one static prompt (dispatch/gate.py's
BANKING_AGENT, and this module's old module-level SYSTEM_PROMPT). Issue #20 replaces that with a
table: a caller starts on TRIAGE, which has no banking tools of its own, and is handed off to
BANKING mid-call -- the same realtime session reconfigured via session.update, never a second
session (docs/PLAN.md decision 6: "One persistent realtime session per call; agent swap via
session.update").

Only two agents exist because only one specialist's tools exist: docs/PLAN.md decision 6 names a
longer chain (Triage -> Accounts -> Cards), but "Cards" has no tools behind it yet -- block_card is
decision 5's stated future scope, not something dispatch/tools.py declares today. Adding a real
Cards specialist later is a new AgentSpec row plus new tools in dispatch/tools.py, not a change to
this module's shape, session.py's handoff handling, or the gate (issue #20's acceptance criterion:
"adding an agent requires no change to enforcement or dispatch logic").

**Tool scope here is defence in depth, not the control** -- dispatch/gate.py's own docstring says
this directly. Narrowing which tools an agent's session.update declares reduces what the model is
likely to attempt; only dispatch/gate.py's is_allowed() decides whether an attempt succeeds, and it
never reads this module.
"""
from dataclasses import dataclass

from ..dispatch import gate
from ..dispatch.tools import TOOLS

# Every handoff tool is named this way, so handoff_target() can recognise one without a second,
# hand-maintained list of tool names to keep in sync with AGENTS.
_HANDOFF_PREFIX = "handoff_to_"


@dataclass(frozen=True)
class AgentSpec:
    """One agent: who it is, what it's told, and which declared tools it may reach.

    `identity` is the value dispatch/gate.py's PERMISSIONS table keys on -- the same string has to
    appear there for a permission row to ever mean anything. `tool_names` is a subset of
    dispatch.tools.TOOLS's names (defence in depth, not enforcement -- see module docstring).
    `handoff_to` is the set of other identities in AGENTS this agent can transfer the call to.
    """

    identity: str
    instructions: str
    tool_names: frozenset[str] = frozenset()
    handoff_to: frozenset[str] = frozenset()


TRIAGE = AgentSpec(
    identity=gate.TRIAGE_AGENT,
    instructions=(
        "You are the first point of contact on a phone banking call. Greet the caller briefly "
        "and ask what they need. You have no banking tools of your own -- for anything about a "
        "balance or moving money, hand the call to the banking specialist right away rather than "
        "trying to help directly or making the caller repeat themselves once you do."
    ),
    tool_names=frozenset(),
    handoff_to=frozenset({gate.BANKING_AGENT}),
)

BANKING = AgentSpec(
    identity=gate.BANKING_AGENT,
    instructions=(
        "You are a phone banking specialist, continuing a call the triage agent already greeted -- "
        "don't greet the caller again, just continue. Be brief and clear, like a real phone call. "
        "Always use the tools to check a balance or make a transfer -- never state a balance or "
        "confirm a transfer without calling the matching tool first. If a transfer can't go "
        "through, say why and state the actual available amount."
    ),
    tool_names=frozenset({"get_balance", "transfer", "list_accounts"}),
    handoff_to=frozenset(),
)

#: Every agent that exists, keyed by identity. session.py and this module's own helpers below are
#: the only readers -- neither branches on which agent it has, both just look this table up.
AGENTS = {spec.identity: spec for spec in (TRIAGE, BANKING)}


def handoff_tool_name(target_identity):
    """The synthetic tool name a handoff to `target_identity` is declared and invoked under."""
    return f"{_HANDOFF_PREFIX}{target_identity}"


def handoff_target(tool_name, from_identity):
    """The agent identity `tool_name` would hand the call off to *from `from_identity`*, or None
    if it isn't a handoff tool, names an agent that doesn't exist, or isn't an edge `from_identity`
    actually declares in its own `handoff_to`. session.py uses this to route a function call: a
    handoff never reaches dispatch_tool_call, since it isn't a banking tool and has no gate opinion
    of its own -- which is exactly why this function, not the gate, has to be the thing that checks
    the edge is real. Checking only "does the target exist in AGENTS" (dropped 2026-09-07,
    /code-review of #20) would let any agent claim to hand off to any other agent regardless of
    its own declared `handoff_to` -- BANKING has none, so a hallucinated handoff_to_triage call
    while on BANKING would have silently reconfigured the session with no check at all."""
    if not tool_name.startswith(_HANDOFF_PREFIX):
        return None
    target = tool_name[len(_HANDOFF_PREFIX):]
    if target not in AGENTS:
        return None
    return target if target in AGENTS[from_identity].handoff_to else None


def _handoff_tool_declaration(target_identity):
    return {
        "type": "function",
        "name": handoff_tool_name(target_identity),
        "description": (
            f"Transfer this call to the {target_identity} agent. Use this once you know what the "
            "caller needs and it isn't something you handle yourself."
        ),
        "parameters": {"type": "object", "properties": {}, "required": []},
    }


def tools_for(identity):
    """Every tool `identity`'s session.update should declare: its real banking tools (filtered
    from dispatch.tools.TOOLS by name, the same master list dispatch/gate.py's own tests are
    driven off) plus one synthetic handoff tool per agent it can transfer to."""
    spec = AGENTS[identity]
    real_tools = [tool for tool in TOOLS if tool["name"] in spec.tool_names]
    handoff_tools = [_handoff_tool_declaration(target) for target in sorted(spec.handoff_to)]
    return real_tools + handoff_tools

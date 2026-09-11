"""The declarative agent table (issue #20): identity, instructions, tool scope -- data, not code.

Phase 1 and Phase 2.1-2.3 had exactly one agent and one static prompt (dispatch/gate.py's
BANKING_AGENT, and this module's old module-level SYSTEM_PROMPT). Issue #20 replaces that with a
table: a caller starts on TRIAGE, which has no banking tools of its own, and is handed off to
BANKING mid-call -- the same realtime session reconfigured via session.update, never a second
session (docs/PLAN.md decision 6: "One persistent realtime session per call; agent swap via
session.update").

**Three agents since Phase 5** (issue #47): triage, banking, and cards. For three phases there were
two, because Cards had no tools behind it -- `block_card` was decision 5's stated future scope, and
an agent with no tools is a row that proves nothing. Issue #20's acceptance criterion said adding one
would be "a new AgentSpec row plus new tools in dispatch/tools.py, not a change to this module's
shape, session.py's handoff handling, or the gate". Phase 5 is where that was tested rather than
asserted, and it held: the third agent cost a row here, a row in dispatch/gate.py's PERMISSIONS, and
nothing else.

Triage declares an edge to both specialists. Neither specialist declares an edge to anything --
including to each other. A caller who has been handed to Cards and then asks about a balance cannot
be routed onward by a model that decides to; `handoff_target()` checks the edge against the *calling*
agent's own `handoff_to`, so an undeclared handoff falls through to the gate and is refused like any
other unrecognised tool name.

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
        "You are the first point of contact on a phone banking call. Greet the caller briefly, "
        "then ask them to key their four-digit PIN on the phone's keypad. "
        "Never ask them to say the PIN out loud, never read any digit back to them, and never "
        "repeat or acknowledge individual key presses. You do not see the digits and you do not "
        "check them -- the system does that on its own and will tell you the result. "
        "If you are told the PIN was wrong, ask them to key it again without saying anything "
        "about how many tries are left. "
        "You have no banking tools of your own. For anything about a balance, recent activity or "
        "moving money, hand the call to the banking agent right away. If the caller's card is "
        "lost or stolen, or they want it stopped, hand the call to the cards agent right away. "
        "Either way, do it rather than trying to help directly, and don't make the caller repeat "
        "themselves once you do."
    ),
    tool_names=frozenset(),
    handoff_to=frozenset({gate.BANKING_AGENT, gate.CARDS_AGENT}),
)

BANKING = AgentSpec(
    identity=gate.BANKING_AGENT,
    instructions=(
        "You are a phone banking specialist, continuing a call the triage agent already greeted -- "
        "don't greet the caller again, just continue. Be brief and clear, like a real phone call. "
        "Always use the tools to check a balance, list recent activity or make a transfer -- "
        "never state a balance, describe activity or confirm a transfer without calling the "
        "matching tool first. If a transfer can't go through, say why and state the actual "
        "available amount."
    ),
    tool_names=frozenset({"get_balance", "transfer", "list_accounts", "list_transactions"}),
    handoff_to=frozenset(),
)

CARDS = AgentSpec(
    identity=gate.CARDS_AGENT,
    instructions=(
        "You handle lost and stolen cards on a phone banking call, continuing a call the triage "
        "agent already greeted -- don't greet the caller again, just continue. Be brief and "
        "clear, like a real phone call. "
        # The confirmation is the model's, and it is stated in two places on purpose -- here and in
        # the tool's own description (dispatch/tools.py). It is deliberately NOT a second tool call
        # and NOT a state the gate knows about: putting a conversational step inside the control
        # would give the gate a second job, and the gate has exactly one.
        "Before you block a card, say plainly that blocking cannot be undone on this line and ask "
        "the caller to confirm they want it blocked. Only call block_card once they have "
        "confirmed. "
        # Said here rather than left to the model's instincts: a caller who asks twice, or whose
        # first request the agent is unsure about, must not be talked out of the most urgent thing
        # they can ask for. The idempotency key makes a second call safe, so the honest answer to
        # "did that work" is to call the tool again.
        "If the caller asks again, or you are not sure the block went through, call block_card "
        "again -- it is safe to repeat and will tell you if the card was already blocked. "
        "If you are told it was already blocked, say so plainly rather than saying you have just "
        "blocked it."
    ),
    tool_names=frozenset({"block_card"}),
    handoff_to=frozenset(),
)

#: Every agent that exists, keyed by identity. session.py and this module's own helpers below are
#: the only readers -- neither branches on which agent it has, both just look this table up.
#:
#: Three since Phase 5 (issue #47). Adding CARDS required a row here, a row in dispatch/gate.py's
#: PERMISSIONS, and nothing else -- not session.py's handoff handling, not `is_allowed()`, not
#: `handoff_target()`. That was issue #20's acceptance criterion stated as a claim three phases ago
#: and it is now a claim that has been tested.
AGENTS = {spec.identity: spec for spec in (TRIAGE, BANKING, CARDS)}


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

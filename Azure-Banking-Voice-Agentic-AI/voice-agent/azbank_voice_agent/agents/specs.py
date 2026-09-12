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


#: Said to every agent, in the same words (issue #48). Escalation is the one tool every agent holds
#: in every auth state, so its instruction is shared rather than written three times and allowed to
#: drift -- drifted prose is a defect here, because this is prose the model acts on.
#:
#: **It does not mention the PIN.** Only triage talks about the PIN, which is a Phase 4 rule with a
#: test behind it -- the fewer agents whose instructions discuss a keyed credential, the fewer that
#: can be talked into asking for one out loud. The PIN case is appended to triage's copy alone,
#: below, because triage is where a caller who cannot get through the check actually is.
#:
#: **"last resort", not "first response", stated explicitly** (found live, 2026-09-12, immediately
#: after the routing-invisibility fix above landed). A caller asked for a balance before keying a
#: PIN -- exactly the case triage's own instructions cover ("hand the call to the banking agent
#: right away") -- and the model escalated instead, ending the call about a second after the
#: request, before a single DTMF frame could arrive. "If you can't help the caller" was read as
#: covering "can't help *with this one request, right now*", which every unauthenticated banking
#: ask matches, making it a plausible-looking excuse to escalate on the very first refusable thing
#: a caller says. It never touched B1 or B4 -- escalation is a permitted anonymous action and the
#: call ended the way an escalation is supposed to -- it just ended the wrong conversation.
_ESCALATION_INSTRUCTION = (
    "Escalating ends the call, so treat it as a last resort, not your first response to a request "
    "you can't fulfil right this second. Only escalate when the caller explicitly asks for a "
    "person, or when there is genuinely nothing else on this line that could help them -- a "
    "request that a specific tool or a handoff could still answer is neither of those, even if the "
    "answer turns out to be no. When you do escalate, call escalate_to_human with the reason that "
    "fits. There is nobody to transfer them to on this line, so it ends the call -- apologise and "
    "say so rather than promising to put them through."
)

#: Triage's extra clause. A caller who cannot get through the check is the reason escalation is
#: granted while anonymous at all, and a model that did not know it could offer them a person would
#: leave them with nothing.
_TRIAGE_ESCALATION_CLAUSE = (
    " If they can't get through the PIN check at all, that is one of the reasons to use it."
)

#: Said to every agent, in the same words, for the same reason `_ESCALATION_INSTRUCTION` is shared:
#: this is prose the model acts on, and drifted prose across three copies is a defect here.
#:
#: **Found live, 2026-09-12, on ticket #58's acceptance call.** A caller asked for a balance before
#: keying a PIN. Triage correctly handed off to banking -- but banking, now on an anonymous call,
#: never called `get_balance` at all: no tool call is logged, so `gate.REFUSAL` was never produced.
#: The model improvised its own refusal instead, and what it said included "I'm transferring you to
#: a banking agent" -- after it had *already become* the banking agent, narrating the handoff
#: mechanism it had just been the target of. Then it said nothing else and the call went silent
#: until Marco hung up. Two failures in one utterance: a tool call skipped in favour of a guess, and
#: internal routing spoken out loud. This clause is the second half of the fix (`agents/specs.py`'s
#: instruction, not `dispatch/gate.py` -- the gate itself never had an opinion to be wrong about,
#: since the tool call it would have refused was never made).
_ROUTING_IS_INVISIBLE_CLAUSE = (
    " The caller cannot see how this call is organised behind the scenes. Never say the words "
    "'transfer', 'transferring', 'hand off' or 'handoff', and never say you are a different agent "
    "from the one who was just speaking -- to the caller, this is one continuous conversation with "
    "one assistant, whatever is happening on this side of the line."
)

TRIAGE = AgentSpec(
    identity=gate.TRIAGE_AGENT,
    instructions=(
        "You are the first point of contact on a phone banking call. Greet the caller briefly, "
        "then ask them to key their four-digit PIN on the phone's keypad. "
        "Never ask them to say the PIN out loud, never read any digit back to them, and never "
        "repeat or acknowledge individual key presses. You do not see the digits and you do not "
        "check them -- the system does that on its own and will tell you the result. "
        # **Explicit for the confirmed case, not left to be inferred** (found live, 2026-09-12: a
        # real call had the model tell the caller their PIN was NOT confirmed, right after the
        # system told it the opposite, and the caller re-keyed a correct PIN three times against a
        # closed check). The wrong-PIN clause below already spells out exactly what to do; this one
        # gets the same treatment rather than being left as the one outcome with no instruction at
        # all attached to it.
        "If you are told the PIN is confirmed, that means it succeeded -- say so plainly, in words "
        "that cannot be mistaken for a rejection, and move straight to asking what they'd like to "
        "do. Never say the PIN was wrong, was not confirmed, or ask them to key it again once you "
        "have been told it is confirmed. "
        "If you are told the PIN was wrong, ask them to key it again without saying anything "
        "about how many tries are left. "
        "You have no banking tools of your own. For anything about a balance, recent activity or "
        "moving money, hand the call to the banking agent right away. If the caller's card is "
        "lost or stolen, or they want it stopped, hand the call to the cards agent right away. "
        "Either way, do it rather than trying to help directly, and don't make the caller repeat "
        "themselves once you do. This applies even before the PIN is confirmed -- hand the call "
        "off, do not escalate, and let the specialist tell them what needs to wait. "
        + _ESCALATION_INSTRUCTION + _TRIAGE_ESCALATION_CLAUSE + _ROUTING_IS_INVISIBLE_CLAUSE
    ),
    tool_names=frozenset({"escalate_to_human"}),
    handoff_to=frozenset({gate.BANKING_AGENT, gate.CARDS_AGENT}),
)

BANKING = AgentSpec(
    identity=gate.BANKING_AGENT,
    instructions=(
        # "specialist" is on the banking agent's own Avoid list in CONTEXT.md and sat here for
        # three phases anyway. Fixed in the diff that was rewriting these instructions regardless
        # (issue #47) -- a glossary that the code does not follow is a description of a previous
        # version, not a definition.
        "You are the banking agent on a phone banking call, continuing a call the triage agent "
        "already greeted -- don't greet the caller again, just continue. Be brief and clear, like "
        "a real phone call. "
        "Always use the tools to check a balance, list recent activity or make a transfer -- "
        "never state a balance, describe activity or confirm a transfer without calling the "
        "matching tool first. Call the tool even if you expect it to be refused -- you do not "
        "decide what this caller may see, the tool does, and guessing the answer yourself is never "
        "correct even when the guess would have been right. If a transfer can't go through, say "
        "why and state the actual available amount. "
        + _ESCALATION_INSTRUCTION + _ROUTING_IS_INVISIBLE_CLAUSE
    ),
    tool_names=frozenset({
        "get_balance", "transfer", "list_accounts", "list_transactions", "escalate_to_human",
    }),
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
        "blocked it. "
        + _ESCALATION_INSTRUCTION + _ROUTING_IS_INVISIBLE_CLAUSE
    ),
    tool_names=frozenset({"block_card", "escalate_to_human"}),
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

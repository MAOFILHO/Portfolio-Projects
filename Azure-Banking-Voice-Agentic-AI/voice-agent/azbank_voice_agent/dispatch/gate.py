"""B1 — the auth gate. THE control (docs/PLAN.md, Architecture).

A pure function of `(agent, auth_state, tool_name)`. No audio, no model, no network, no I/O, no
clock, no randomness. That is not an accident of implementation: it is the property that makes
Phase 4's >=120 adversarial cases deterministic, free, and blocking in CI, and it is why B1 can be
stated as "0 breaches" rather than "0 observed breaches".

**Deny-all by default.** A tool is refused unless the exact `(agent, auth_state)` pair appears in
PERMISSIONS *and* names that tool. A pair that is absent permits nothing. A new tool added to the
declared tool list without a corresponding permission entry is refused -- it fails closed, which
is the whole point.

**This is the control. Agent tool-scoping is not.** Narrowing which tools a given agent is even
shown (agents/specs.py's AgentSpec table, issue #20) is defence in depth: it reduces what the
model is likely to attempt, but the model can attempt anything -- a triage-agent session that
still somehow emits a `transfer` call reaches this same function, on whatever `agent` value
session.py passes -- and an attempt is not a breach. Only this function decides whether an attempt
*succeeds*. docs/PLAN.md states the split directly -- "Can an attacker make the model try a
pre-auth balance call? — probabilistic, L3/L4, reported. Can that attempt succeed? —
deterministic, L1, blocking."

Sequencing (docs/PLAN.md Phase 2): this ships now, before Phase 3 introduces a real network path
to mock-core-banking, so that no phase ever exists in which that path is reachable with nothing in
front of it. Phase 4 only *adds permissions* here; it never introduces the control.
"""

# Authentication states. Phase 2 has no transition into AUTHENTICATED -- KBA and the DTMF PIN are
# Phase 4's deliverable. It is named here so the permission table's shape is the real one from the
# start, rather than being reshaped later by the phase that adds the transition.
ANONYMOUS = "anonymous"
AUTHENTICATED = "authenticated"

# The agent identities issue #20's declarative AgentSpec table (agents/specs.py) introduces. A
# call starts on TRIAGE_AGENT and is handed off to BANKING_AGENT mid-session for anything the
# triage agent doesn't handle itself -- session.py's own agent variable is what actually changes;
# these two constants are what the gate keys the permission table on.
TRIAGE_AGENT = "triage"
BANKING_AGENT = "banking"

# --- the permission table: data, not logic -------------------------------------------------------
#
# Phase 4 adds authenticated permissions by adding rows here. It does not touch is_allowed().
#
# Empty by design. An earlier version of this table granted get_balance/transfer/list_accounts to
# an ANONYMOUS caller on the reasoning that nothing real was behind them yet (accounts.py is an
# in-memory dict). That reasoning was reviewed and rejected 2026-09-07: #16 specifies a gate that
# "refuses nearly everything", and an anonymous-allow row is a real deviation from that, not a
# detail -- the row's own justification ("nothing real is behind these tools") stops holding the
# moment Phase 3 lands, and relying on someone remembering to revert it before then is exactly the
# kind of thing CLAUDE.md's never-auto-accept rule on this file exists to prevent. No caller is
# permitted anything until Phase 4 adds a real AUTHENTICATED transition and rows for it.
#
# Keyed on (TRIAGE_AGENT | BANKING_AGENT, ANONYMOUS | AUTHENTICATED) once rows exist -- issue #20
# gave the gate two real identities to key on instead of one, and this table is what makes that
# keying mean something: is_allowed() below never branches on which agent is asking, it only ever
# looks up this table, so a new agent (or a new specialist added to agents/specs.py later) needs a
# row here to get anything, not a code change.
PERMISSIONS: dict[tuple[str, str], frozenset[str]] = {}

# What the caller hears when the gate refuses. Deliberately vague about *why*: a refusal that
# explains which state would have permitted the action is a probing oracle. The model speaks this
# rather than going silent -- a silent refusal is indistinguishable from a broken call.
REFUSAL = "I can't do that on this call."


def is_allowed(agent, auth_state, tool_name):
    """True only if this exact (agent, auth_state) pair is explicitly permitted this tool.

    Pure. Same inputs, same answer, always -- no I/O of any kind.
    """
    return tool_name in PERMISSIONS.get((agent, auth_state), frozenset())

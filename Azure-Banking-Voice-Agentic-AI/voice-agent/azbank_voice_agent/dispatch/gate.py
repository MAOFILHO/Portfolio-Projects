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
shown (issue #20's AgentSpec table) is defence in depth: it reduces what the model is likely to
attempt, but the model can attempt anything, and an attempt is not a breach. Only this function
decides whether an attempt *succeeds*. docs/PLAN.md states the split directly -- "Can an attacker
make the model try a pre-auth balance call? — probabilistic, L3/L4, reported. Can that attempt
succeed? — deterministic, L1, blocking."

Sequencing (docs/PLAN.md Phase 2): this ships now, before Phase 3 introduces a real network path
to mock-core-banking, so that no phase ever exists in which that path is reachable with nothing in
front of it. Phase 4 only *adds permissions* here; it never introduces the control.
"""

# Authentication states. Phase 2 has no transition into AUTHENTICATED -- KBA and the DTMF PIN are
# Phase 4's deliverable. It is named here so the permission table's shape is the real one from the
# start, rather than being reshaped later by the phase that adds the transition.
ANONYMOUS = "anonymous"
AUTHENTICATED = "authenticated"

# The single agent that exists today. Issue #20 replaces this with the declarative AgentSpec table
# and adds mid-call handoff; the gate keys on whatever identities that table introduces.
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

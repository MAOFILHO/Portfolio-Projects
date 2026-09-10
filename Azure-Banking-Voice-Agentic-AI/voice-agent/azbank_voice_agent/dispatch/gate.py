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

Sequencing (docs/PLAN.md Phase 2): this shipped before Phase 3 introduced a real network path to
mock-core-banking, so that no phase ever existed in which that path was reachable with nothing in
front of it. Phase 4 only *added permissions* here; it never introduced the control, and
is_allowed() is unchanged from the day it was written.

**B1, as of Phase 4** (`docs/phase4/exit-criteria.md`, approved 2026-09-10): no *banking* operation
-- balance, transfer, or list -- reaches the core-banking client while the call's auth state is not
authenticated. PIN verification is the only operation reachable while anonymous, and it does not
come through here at all: it has no tool, and the call's authenticator holds the client directly.
The earlier wording, "zero authenticated-only tool invocations", was written when nothing legitimate
could reach that client before authentication, and a detector reading it literally would have scored
the PIN check itself as a breach.
"""

# Authentication states. Named here since Phase 2, before anything could reach the second one, so
# that the permission table's shape was the real one from the start rather than being reshaped by
# the phase that added the transition. Phase 4 added that transition: a call becomes AUTHENTICATED
# when the caller keys a PIN the system of record accepts (auth/, realtime/session.py). Binary, with
# nothing in between -- how many digits have arrived is private to the authenticator and is not a
# third value of this.
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
# Phase 4 (issue #38) opened this table for the first time, by adding rows. It did not touch
# is_allowed(), deliberately: widening B1 has to be visibly a data change rather than a logic one.
#
# **All four (agent, auth_state) pairs are written out, including the three that grant nothing.**
# is_allowed() treats an absent key and an empty set identically, so the three empty rows change no
# behaviour at all -- they are here so the table states its own completeness. A reader can see that
# every pair was considered, rather than inferring it from what is missing, and a fourth agent added
# later is visibly absent instead of quietly denied for a reason nobody wrote down.
#
# **One row grants anything.** The banking agent, on a call that has passed a PIN check, gets the
# three tools that already exist. That is the whole of what this phase unlocked:
#
#     triage  + anonymous       -> nothing
#     triage  + authenticated   -> nothing
#     banking + anonymous       -> nothing
#     banking + authenticated   -> get_balance, transfer, list_accounts
#
# Triage grants nothing in either state because it has no banking tools of its own -- authenticating
# does not change what triage is for. Banking grants nothing while anonymous because routing is not
# authorization: a caller may be handed to the banking agent before authenticating, and is refused
# everything there. Handoff itself stays outside this table; gating it would put a routing decision
# inside the control and give the gate a second job.
#
# **There is no row for a PIN check, because there is no tool for one.** The spoken second factor
# was cut at Phase 4 kickoff, which removed the one tool that would have had to be callable before
# authentication. Verification reaches the core-banking client directly from the call's
# authenticator, never through a tool call, so no tool at all is reachable while a call is anonymous
# -- and that is what B1's sharpened breach definition asserts.
#
# Keyed on (TRIAGE_AGENT | BANKING_AGENT, ANONYMOUS | AUTHENTICATED) -- issue #20 gave the gate two
# real identities to key on instead of one, and this table is what makes that keying mean something:
# is_allowed() below never branches on which agent is asking, it only ever looks up this table, so a
# new agent (or a new specialist added to agents/specs.py later) needs a row here to get anything,
# not a code change.
#
# The history that shaped it: an earlier version granted these same three tools to an ANONYMOUS
# caller on the reasoning that nothing real was behind them yet. That was reviewed and rejected
# 2026-09-07, and the table shipped empty for two phases so that no phase ever existed in which a
# real network path to the system of record was reachable with nothing in front of it.
PERMISSIONS: dict[tuple[str, str], frozenset[str]] = {
    (TRIAGE_AGENT, ANONYMOUS): frozenset(),
    (TRIAGE_AGENT, AUTHENTICATED): frozenset(),
    (BANKING_AGENT, ANONYMOUS): frozenset(),
    (BANKING_AGENT, AUTHENTICATED): frozenset({"get_balance", "transfer", "list_accounts"}),
}

# What the caller hears when the gate refuses. Deliberately vague about *why*: a refusal that
# explains which state would have permitted the action is a probing oracle. The model speaks this
# rather than going silent -- a silent refusal is indistinguishable from a broken call.
REFUSAL = "I can't do that on this call."


def is_allowed(agent, auth_state, tool_name):
    """True only if this exact (agent, auth_state) pair is explicitly permitted this tool.

    Pure. Same inputs, same answer, always -- no I/O of any kind.
    """
    return tool_name in PERMISSIONS.get((agent, auth_state), frozenset())

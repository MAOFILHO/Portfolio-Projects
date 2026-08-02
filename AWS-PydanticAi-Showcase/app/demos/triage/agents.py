"""The triage agent: one agent, three tools, one discriminated-union output.

This demo exists to show `deps_type` doing real work. The agent knows nothing
about customers; it can only *ask*, via tools that read `RunContext.deps`. Swap
the deps and the same agent triages a different tenant's tickets — which is also
why the tests can drive it with fixture accounts and no network at all.
"""

from __future__ import annotations

from textwrap import dedent

from pydantic_ai import Agent, RunContext

from app.shared.config import FAST_MODEL, FAST_SETTINGS

from .models import Account, Escalate, NeedsInfo, PastTicket, Resolve, TriageDeps

triage_agent = Agent(
    FAST_MODEL,
    name="triage_agent",
    deps_type=TriageDeps,
    # A sequence, not `Resolve | Escalate | NeedsInfo`: Pydantic AI's `output_type`
    # takes a sequence of candidate types (it generates one output tool per entry,
    # and the model picks a branch by choosing a tool), and only the sequence form
    # carries the member types through to `result.output` for a type checker.
    output_type=[Resolve, Escalate, NeedsInfo],
    model_settings=FAST_SETTINGS,
    instructions=dedent(
        """
        You are a front-line support engineer triaging an inbound ticket.

        Always look up the account first — plan, spend, SLA, and whether an
        incident is already open change what the right call is. Check recent
        tickets when the report sounds like it might be a recurrence.

        Then choose exactly one outcome:
        - resolve: you can answer the customer correctly right now, from the
          ticket alone. Write the full reply.
        - escalate: it needs a specialist team. Pick the team and a severity
          justified by customer impact *and* the account's SLA.
        - needs_info: the ticket is too vague to action. Ask the specific
          questions that would unblock it — never guess at what they meant.
        """
    ),
)


@triage_agent.tool
async def lookup_account(ctx: RunContext[TriageDeps]) -> Account | str:
    """Fetch the plan, seat count, spend, SLA, and open-incident count for this ticket's account."""
    if ctx.deps.progress:
        await ctx.deps.progress("Triage agent: looking up account")
    account = ctx.deps.accounts.get(ctx.deps.account_id)
    return account if account is not None else f"No account found for {ctx.deps.account_id}"


@triage_agent.tool
async def recent_tickets(ctx: RunContext[TriageDeps]) -> list[PastTicket]:
    """List this account's recent support tickets, to spot recurrences."""
    if ctx.deps.progress:
        await ctx.deps.progress("Triage agent: pulling recent tickets")
    return ctx.deps.tickets.get(ctx.deps.account_id, [])


@triage_agent.tool
async def check_entitlement(ctx: RunContext[TriageDeps], feature: str) -> str:
    """Check whether the account's plan entitles it to a given feature.

    Args:
        feature: The feature the customer is asking about, e.g. "sso" or "audit-log".
    """
    if ctx.deps.progress:
        await ctx.deps.progress("Triage agent: checking entitlement")
    account = ctx.deps.accounts.get(ctx.deps.account_id)
    if account is None:
        return f"No account found for {ctx.deps.account_id}"
    entitlements = {
        "free": {"core"},
        "business": {"core", "audit-log"},
        "enterprise": {"core", "audit-log", "sso", "priority-routing"},
    }
    included = feature.lower() in entitlements[account.plan]
    verdict = "included in" if included else "NOT included in"
    return f"'{feature}' is {verdict} the {account.plan} plan."


# The tools the agent may choose to call, as opposed to the output tools Pydantic
# AI generates to capture structured output. Because `TriageDecision` is a union,
# there is one output tool *per member* (`final_result_Resolve`,
# `final_result_Escalate`, ...), so the UI's "tools the agent called" trace can't
# be built by excluding a single well-known name — it has to include known tools
# rather than exclude generated ones. `test_classify_endpoint_returns_the_decision_
# and_the_tool_trace` pins the exact trace, so this can't drift unnoticed.
TOOL_NAMES = frozenset({"lookup_account", "recent_tickets", "check_entitlement"})

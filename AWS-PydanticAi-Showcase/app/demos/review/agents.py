"""Agent-as-tool delegation — the counterpoint to Research Analyst's graph.

Research Analyst fans out to parallel workers through an explicit `pydantic_graph`
node. This demo fans out to three specialists through *tool calls*: the lead
reviewer decides which specialists to consult, and each tool runs a sub-agent.

The two shapes are not interchangeable, and the difference is the point:

- A graph is right when the control flow is *yours* — a fixed sequence, a
  bounded retry loop, a step that must not run until another finished. It's
  inspectable, diagrammable, and testable without a model in the loop.
- Delegation is right when the control flow is *the model's* — when which
  specialists to consult, and whether to consult any at all, is itself the
  judgment call you're paying the model to make.

Delegation costs you a bounded budget: each sub-agent run is more requests, and
a confused lead reviewer can loop. Hence `usage=ctx.usage` on every delegated
run, so all of it bills to one budget the caller caps with `UsageLimits`.
"""

from __future__ import annotations

from textwrap import dedent

from pydantic_ai import Agent, RunContext

from app.shared.config import FAST_MODEL, FAST_SETTINGS

from .models import ReviewDeps, ReviewVerdict, SpecialistFindings

# Bounds the whole delegated run: the lead reviewer's own turns plus every
# sub-agent request. Three specialists, each of which may take a turn or two,
# plus the lead's opening and closing turns, fits comfortably under this — and
# a runaway delegation loop hits the ceiling instead of the credit card.
REQUEST_LIMIT = 12


def _specialist(name: str, brief: str) -> Agent[ReviewDeps, SpecialistFindings]:
    return Agent(
        FAST_MODEL,
        name=name,
        deps_type=ReviewDeps,
        output_type=SpecialistFindings,
        model_settings=FAST_SETTINGS,
        instructions=dedent(brief),
    )


style_agent = _specialist(
    "style_agent",
    """
    You review diffs for readability and maintainability only: naming, dead
    code, duplicated logic, confusing control flow, missing or misleading
    comments. Do not comment on security or tests — other reviewers cover those.
    Cite real file paths and line numbers from the diff. If the diff is clean by
    your standard, return no comments and say so.
    """,
)

security_agent = _specialist(
    "security_agent",
    """
    You review diffs for security defects only: injection (SQL, shell, template),
    missing authentication or authorization checks, secrets committed in source,
    unsafe deserialization, path traversal, and leaking sensitive data into logs
    or errors. Rate anything exploitable by an unauthenticated caller as critical.
    Cite real file paths and line numbers. Do not speculate about code you can't
    see in the diff.
    """,
)

tests_agent = _specialist(
    "tests_agent",
    """
    You review diffs for test coverage only: new behavior landing without a test,
    error paths and edge cases left unexercised, and tests that assert nothing
    meaningful. Name the specific case that is missing, not "add more tests".
    Cite real file paths and line numbers.
    """,
)

lead_reviewer_agent = Agent(
    FAST_MODEL,
    name="lead_reviewer_agent",
    deps_type=ReviewDeps,
    output_type=ReviewVerdict,
    model_settings=FAST_SETTINGS,
    instructions=dedent(
        """
        You are the lead reviewer on a pull request. Consult the specialist
        reviewers available to you as tools — normally all three, but skip any
        that clearly cannot apply to this diff.

        Then consolidate. Merge duplicate findings, drop anything a specialist
        raised that the diff doesn't actually support, and decide:
        - request_changes: at least one major or critical finding
        - comment: only minor or informational findings
        - approve: nothing worth blocking or noting

        Keep every comment you carry through, with its file, line, severity and
        category intact.
        """
    ),
)


async def _delegate(
    ctx: RunContext[ReviewDeps], agent: Agent[ReviewDeps, SpecialistFindings], label: str
) -> SpecialistFindings:
    """Run a specialist against the injected diff, billing it to the caller's budget.

    `usage=ctx.usage` is the load-bearing argument: without it each sub-agent run
    would keep its own tally and the `UsageLimits` the caller set on the outer run
    would only ever bound the lead reviewer's own turns. `label` drives the
    progress log the UI streams — reported around the call so the specialists'
    parallel start and (genuinely different) finish times both show up.
    """
    if ctx.deps.progress:
        await ctx.deps.progress(f"{label}: analyzing diff")
    result = await agent.run(
        f"Review this diff:\n\n{ctx.deps.diff}", deps=ctx.deps, usage=ctx.usage
    )
    if ctx.deps.progress:
        await ctx.deps.progress(f"{label}: done")
    return result.output


@lead_reviewer_agent.tool
async def review_style(ctx: RunContext[ReviewDeps]) -> SpecialistFindings:
    """Ask the style reviewer about readability and maintainability."""
    return await _delegate(ctx, style_agent, "Style reviewer")


@lead_reviewer_agent.tool
async def review_security(ctx: RunContext[ReviewDeps]) -> SpecialistFindings:
    """Ask the security reviewer about injection, authz, secrets, and data leaks."""
    return await _delegate(ctx, security_agent, "Security reviewer")


@lead_reviewer_agent.tool
async def review_tests(ctx: RunContext[ReviewDeps]) -> SpecialistFindings:
    """Ask the test reviewer about coverage gaps in the changed behavior."""
    return await _delegate(ctx, tests_agent, "Tests reviewer")

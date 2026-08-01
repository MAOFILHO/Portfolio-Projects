"""The deterministic multi-agent pipeline, expressed as a `pydantic_graph` graph.

    plan -> fan-out (parallel research workers) -> synthesize -> evaluate
                                                        ^              |
                                                        |   fail (<3x) |
                                                        +--- revise <--+

`Evaluate` ends the graph once the draft passes (or the revision budget is
exhausted), returning a `ResearchReport` that still needs human compliance
sign-off. That sign-off happens outside the graph, in this demo's
review/decision endpoints — a human approval is a real-world async boundary,
not something to fake by pausing an in-process graph run.

Each node reports a human-readable status via `PipelineState.progress` before
it starts its work, so callers (see `router.py`) can stream live progress to a
client instead of leaving it staring at a blank screen for the ~1-2 minutes
a real run takes.

See https://ai.pydantic.dev/graph/ for the underlying library.
"""

from __future__ import annotations

import asyncio
import os
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

from pydantic_graph import BaseNode, End, GraphBuilder, GraphRunContext, StepContext

from .agents import evaluator_agent, planner_agent, research_agent, synthesizer_agent
from .models import Finding, ResearchDeps, ResearchReport

# Each retry is a full synth+evaluate round trip and dominates worst-case
# latency; capped low to bound the tail instead of chasing quality forever.
MAX_REVISIONS = int(os.environ.get("SHOWCASE_MAX_REVISIONS", "1"))

ProgressCallback = Callable[[str], Awaitable[None]]


@dataclass
class PipelineState:
    question: str
    deps: ResearchDeps
    progress: ProgressCallback | None = None
    sub_topics: list[str] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)
    report: ResearchReport | None = None
    eval_feedback: str | None = None
    revision_count: int = 0


async def _report(ctx: GraphRunContext[PipelineState, None], message: str) -> None:
    if ctx.state.progress is not None:
        await ctx.state.progress(message)


def _truncate(text: str, limit: int = 60) -> str:
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def _format_findings(findings: list[Finding]) -> str:
    return "\n".join(
        f"- [{f.sub_topic}] {f.summary} (sources: {', '.join(f.sources) or 'none'})"
        for f in findings
    )


async def _run_synthesis(ctx: GraphRunContext[PipelineState, None]) -> ResearchReport:
    prompt = f"Question: {ctx.state.question}\n\nFindings:\n{_format_findings(ctx.state.findings)}"
    if ctx.state.eval_feedback:
        prompt += (
            f"\n\nThe previous draft was rejected by the evaluator: {ctx.state.eval_feedback}\n"
            "Revise accordingly."
        )
    result = await synthesizer_agent.run(prompt, deps=ctx.state.deps)
    return result.output


@dataclass
class PlanSubTopics(BaseNode[PipelineState, None]):
    """Orchestrator: reads the question, plans sub-topics."""

    async def run(self, ctx: GraphRunContext[PipelineState, None]) -> FanOutResearch:
        await _report(ctx, "Orchestrator: planning sub-topics")
        result = await planner_agent.run(ctx.state.question, deps=ctx.state.deps)
        ctx.state.sub_topics = result.output.sub_topics
        return FanOutResearch()


@dataclass
class FanOutResearch(BaseNode[PipelineState, None]):
    """Specialist workers: research each sub-topic in parallel."""

    async def run(self, ctx: GraphRunContext[PipelineState, None]) -> Synthesize:
        await _report(ctx, f"Research: {len(ctx.state.sub_topics)} sub-topics in parallel")

        async def research_one(topic: str) -> list[Finding]:
            result = await research_agent.run(
                f"Research this sub-topic: {topic}", deps=ctx.state.deps
            )
            await _report(ctx, f"Research: done — {_truncate(topic)}")
            return result.output.findings

        results = await asyncio.gather(*(research_one(topic) for topic in ctx.state.sub_topics))
        ctx.state.findings = [finding for findings in results for finding in findings]
        return Synthesize()


@dataclass
class Synthesize(BaseNode[PipelineState, None]):
    """Synthesizer: assemble findings into a draft report."""

    async def run(self, ctx: GraphRunContext[PipelineState, None]) -> Evaluate:
        await _report(ctx, "Synthesizer: drafting report")
        ctx.state.report = await _run_synthesis(ctx)
        return Evaluate()


@dataclass
class Evaluate(BaseNode[PipelineState, None, ResearchReport]):
    """Evaluator: checks the draft against its findings; gates the revision loop."""

    async def run(self, ctx: GraphRunContext[PipelineState, None]) -> Revise | End[ResearchReport]:
        await _report(ctx, "Evaluator: reviewing draft")
        assert ctx.state.report is not None
        draft_json = ctx.state.report.model_dump_json()
        result = await evaluator_agent.run(
            f"Evaluate this draft report against its findings:\n\n{draft_json}"
            f"\n\nFindings:\n{_format_findings(ctx.state.findings)}",
            deps=ctx.state.deps,
        )
        if result.output.passed or ctx.state.revision_count >= MAX_REVISIONS:
            return End(ctx.state.report)
        ctx.state.eval_feedback = result.output.feedback
        ctx.state.revision_count += 1
        return Revise()


@dataclass
class Revise(BaseNode[PipelineState, None]):
    """Revision: fix the draft with the evaluator's feedback, then re-evaluate."""

    async def run(self, ctx: GraphRunContext[PipelineState, None]) -> Evaluate:
        await _report(ctx, f"Synthesizer: revising draft (attempt {ctx.state.revision_count})")
        ctx.state.report = await _run_synthesis(ctx)
        return Evaluate()


builder = GraphBuilder(state_type=PipelineState, output_type=ResearchReport)


@builder.step
async def start(ctx: StepContext[PipelineState, None, None]) -> PlanSubTopics:
    return PlanSubTopics()


builder.add(
    builder.node(PlanSubTopics),
    builder.node(FanOutResearch),
    builder.node(Synthesize),
    builder.node(Evaluate),
    builder.node(Revise),
    builder.edge_from(builder.start_node).to(start),
)

research_pipeline = builder.build()

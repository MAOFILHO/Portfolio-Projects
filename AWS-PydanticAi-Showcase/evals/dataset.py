"""A small, offline-runnable pydantic_evals dataset for the research pipeline.

`analyze()` overrides every agent with `TestModel` so the dataset can be
evaluated in CI with no API key and no network access. Point
`SHOWCASE_RESEARCH_MODEL` at a real model and drop the overrides to evaluate
the actual pipeline instead.
"""

from __future__ import annotations

from dataclasses import dataclass

from pydantic_ai.models.test import TestModel
from pydantic_evals import Case, Dataset
from pydantic_evals.evaluators import Evaluator, EvaluatorContext, EvaluatorOutput

from app.demos.research.agents import (
    evaluator_agent,
    planner_agent,
    research_agent,
    synthesizer_agent,
)
from app.demos.research.models import ResearchDeps, ResearchReport
from app.demos.research.pipeline import PipelineState, research_pipeline


@dataclass
class HasKeyFindings(Evaluator[str, ResearchReport]):
    def evaluate(self, ctx: EvaluatorContext[str, ResearchReport]) -> EvaluatorOutput:
        return {"has_key_findings": len(ctx.output.key_findings) > 0}


@dataclass
class ConfidenceInRange(Evaluator[str, ResearchReport]):
    def evaluate(self, ctx: EvaluatorContext[str, ResearchReport]) -> EvaluatorOutput:
        return {"confidence_in_range": 0 <= ctx.output.confidence <= 1}


async def analyze(question: str) -> ResearchReport:
    with (
        planner_agent.override(model=TestModel()),
        research_agent.override(model=TestModel(), native_tools=[]),
        synthesizer_agent.override(model=TestModel()),
        evaluator_agent.override(model=TestModel()),
    ):
        state = PipelineState(question=question, deps=ResearchDeps())
        return await research_pipeline.run(state=state)


def build_dataset() -> Dataset[str, ResearchReport, None]:
    cases = [
        Case(
            name="vector-db-vs-full-text",
            inputs="What are the tradeoffs between vector databases and full-text search for RAG?",
        ),
        Case(
            name="edge-vs-cloud-inference",
            inputs="When does it make sense to run LLM inference at the edge instead of the cloud?",
        ),
    ]
    return Dataset[str, ResearchReport, None](
        name="research-pipeline",
        cases=cases,
        evaluators=[HasKeyFindings(), ConfidenceInRange()],
    )


if __name__ == "__main__":
    report = build_dataset().evaluate_sync(analyze)
    print(report)

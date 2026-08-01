from pydantic_ai import ModelResponse, ToolCallPart
from pydantic_ai.models.function import AgentInfo, FunctionModel
from pydantic_ai.models.test import TestModel

from app.demos.research.agents import (
    evaluator_agent,
    planner_agent,
    research_agent,
    synthesizer_agent,
)
from app.demos.research.models import ResearchDeps
from app.demos.research.pipeline import PipelineState, research_pipeline


async def test_pipeline_runs_end_to_end_offline():
    state = PipelineState(
        question="What are the tradeoffs between SQL and NoSQL?", deps=ResearchDeps()
    )

    with (
        planner_agent.override(model=TestModel()),
        research_agent.override(model=TestModel(), native_tools=[]),
        synthesizer_agent.override(model=TestModel()),
        evaluator_agent.override(model=TestModel()),
    ):
        report = await research_pipeline.run(state=state)

    assert report.question
    assert isinstance(report.confidence, float)
    assert 0 <= report.confidence <= 1
    assert 0 <= state.revision_count <= 3


async def test_pipeline_retries_on_failed_evaluation():
    """The evaluator fails the first draft, forcing exactly one Revise -> Evaluate loop."""
    call_count = 0

    def flaky_evaluator(messages: list, info: AgentInfo) -> ModelResponse:
        nonlocal call_count
        call_count += 1
        passed = call_count > 1
        args = {"passed": passed, "feedback": "" if passed else "add more sources"}
        return ModelResponse(parts=[ToolCallPart(tool_name=info.output_tools[0].name, args=args)])

    state = PipelineState(
        question="What are the tradeoffs between SQL and NoSQL?", deps=ResearchDeps()
    )

    with (
        planner_agent.override(model=TestModel()),
        research_agent.override(model=TestModel(), native_tools=[]),
        synthesizer_agent.override(model=TestModel()),
        evaluator_agent.override(model=FunctionModel(flaky_evaluator)),
    ):
        report = await research_pipeline.run(state=state)

    assert report.question
    assert call_count == 2
    assert state.revision_count == 1


async def test_pipeline_reports_progress_per_agent():
    messages: list[str] = []

    async def collect(message: str) -> None:
        messages.append(message)

    state = PipelineState(
        question="What are the tradeoffs between SQL and NoSQL?",
        deps=ResearchDeps(),
        progress=collect,
    )

    with (
        planner_agent.override(model=TestModel()),
        research_agent.override(model=TestModel(), native_tools=[]),
        synthesizer_agent.override(model=TestModel()),
        evaluator_agent.override(model=TestModel()),
    ):
        await research_pipeline.run(state=state)

    assert any("Orchestrator" in m for m in messages)
    assert any("Research" in m for m in messages)
    assert any("Synthesizer" in m for m in messages)
    assert any("Evaluator" in m for m in messages)

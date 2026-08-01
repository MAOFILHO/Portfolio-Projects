from pydantic_ai.models.test import TestModel

from app.demos.research.agents import research_agent
from app.demos.research.models import ResearchDeps


def test_research_agent_returns_structured_findings():
    with research_agent.override(model=TestModel(), native_tools=[]):
        result = research_agent.run_sync(
            "Research this sub-topic: vector database tradeoffs",
            deps=ResearchDeps(client_name="Marco"),
        )

    assert result.output.findings
    for finding in result.output.findings:
        assert finding.sub_topic
        assert finding.summary

"""Agents used by the research pipeline (see `app.demos.research.pipeline`).

- `planner_agent` — the orchestrator's planning step: breaks a question into sub-topics.
- `research_agent` — a specialist worker: investigates one sub-topic with web search.
- `synthesizer_agent` — turns findings (plus optional revision feedback) into a `ResearchReport`.
- `evaluator_agent` — gates the revision loop by checking a draft report against its findings.

The pipeline itself (fan-out, evaluate/revise loop, ordering) lives in
`app.demos.research.pipeline` as a `pydantic_graph` graph — see https://ai.pydantic.dev/graph/.
"""

from __future__ import annotations

import os
from textwrap import dedent

from pydantic_ai import Agent
from pydantic_ai.capabilities import WebSearch

from app.shared.config import FAST_MODEL, FAST_SETTINGS

from .models import EvaluationResult, ResearchDeps, ResearchReport, SubTopicFindings, SubTopicPlan

# The one demo that upgrades past the shared FAST_MODEL: open-ended web research
# and multi-source report writing are exactly the tasks where a frontier model
# earns its cost. Planning and evaluation stay on FAST_MODEL — they're simple
# judgment calls, and a smaller model there cuts real wall-clock latency without
# touching the quality of the research or the report itself. (gpt-5.2 has no
# "-mini" sibling, hence FAST_MODEL dropping a generation to gpt-5-mini.)
MODEL = os.environ.get("SHOWCASE_RESEARCH_MODEL", "openai:gpt-5.2")

planner_agent = Agent(
    FAST_MODEL,
    name="planner_agent",
    deps_type=ResearchDeps,
    output_type=SubTopicPlan,
    model_settings=FAST_SETTINGS,
    instructions=dedent(
        """
        You are the lead research analyst planning an investigation.
        Break the user's research question into 2-3 focused, non-overlapping
        sub-topics that, together, cover what's needed to answer it well.
        """
    ),
)

research_agent = Agent(
    MODEL,
    name="research_agent",
    deps_type=ResearchDeps,
    output_type=SubTopicFindings,
    capabilities=[WebSearch(local="duckduckgo", search_context_size="low")],
    instructions=dedent(
        """
        You are a research analyst investigating one sub-topic at a time.
        Use web search to find current, credible information. Return 2-5
        findings, each with a concise summary and the source URLs that back
        it. Prefer primary sources over aggregators.
        """
    ),
)

synthesizer_agent = Agent(
    MODEL,
    name="synthesizer_agent",
    deps_type=ResearchDeps,
    output_type=ResearchReport,
    instructions=dedent(
        """
        You are the lead research analyst synthesizing findings gathered by
        your team into a single ResearchReport: a clear summary, the most
        important findings (deduplicated), a calibrated confidence score,
        and any open questions the research didn't resolve. If told a
        previous draft was rejected, address the feedback directly.
        """
    ),
)

evaluator_agent = Agent(
    FAST_MODEL,
    name="evaluator_agent",
    deps_type=ResearchDeps,
    output_type=EvaluationResult,
    model_settings=FAST_SETTINGS,
    instructions=dedent(
        """
        You are a quality-control evaluator for research reports. Check that:
        - every key finding is backed by at least one source
        - the summary is consistent with, and fully supported by, the key findings
        - the confidence score is justified by the strength and number of findings
        Fail the report (passed=False) with specific, actionable feedback if
        any of these don't hold.
        """
    ),
)

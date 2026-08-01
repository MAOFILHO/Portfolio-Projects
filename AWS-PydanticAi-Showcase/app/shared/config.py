"""Model selection shared across the demos.

Two knobs, not eight: `SHOWCASE_FAST_MODEL` is the default everywhere, and
`SHOWCASE_RESEARCH_MODEL` upgrades only the two steps that genuinely benefit
from a frontier model (open-ended web research and report writing). Triage,
code review, and itinerary planning are short, highly-structured tasks where
the smaller model is both good enough and noticeably faster, which matters
more than marginal quality for a demo someone is watching in real time.
"""

from __future__ import annotations

import os

from pydantic_ai.models.openai import OpenAIChatModelSettings

FAST_MODEL = os.environ.get("SHOWCASE_FAST_MODEL", "openai:gpt-5-mini")

# GPT-5-family models spend variable hidden "reasoning" time before producing
# any output; for simple judgment calls that's often bigger than the cost of
# model size itself. 'minimal' caps that without changing which model runs.
FAST_SETTINGS = OpenAIChatModelSettings(openai_reasoning_effort="minimal")

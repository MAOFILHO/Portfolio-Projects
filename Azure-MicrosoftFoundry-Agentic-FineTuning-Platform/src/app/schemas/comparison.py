"""Schemas for baseline-vs-fine-tuned comparison (Demo 3).

The guide is explicit that fine-tuned output will not match its screenshots
verbatim and that you should "verify that the model follows the intended
travel-assistant behavior" instead. So comparison is scored on *behavioural
assertions*, never string equality.

The three assertions come straight from the training data's own teaching signal:
an exuberant tone, a refusal to recommend hotels/flights/cars/restaurants, and a
closing follow-up question.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, computed_field

Verdict = Literal["pass", "fail"]


class BehaviouralCheck(BaseModel):
    """One assertion evaluated against one response."""

    model_config = ConfigDict(extra="forbid")

    name: str
    description: str
    verdict: Verdict
    evidence: str = ""


class BehaviouralScore(BaseModel):
    """All assertions for a single model's response."""

    model_config = ConfigDict(extra="forbid", protected_namespaces=())

    model_name: str
    response: str
    checks: list[BehaviouralCheck] = Field(default_factory=list)
    latency_ms: int | None = None
    tokens: int | None = None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def passed(self) -> int:
        return sum(1 for c in self.checks if c.verdict == "pass")

    @computed_field  # type: ignore[prop-decorator]
    @property
    def total(self) -> int:
        return len(self.checks)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def score_display(self) -> str:
        return f"{self.passed}/{self.total}"


class PromptComparison(BaseModel):
    """One prompt sent to both models, with both scored."""

    model_config = ConfigDict(extra="forbid")

    prompt: str
    system_prompt: str
    baseline: BehaviouralScore
    fine_tuned: BehaviouralScore

    @computed_field  # type: ignore[prop-decorator]
    @property
    def winner(self) -> Literal["baseline", "fine_tuned", "tie"]:
        if self.fine_tuned.passed > self.baseline.passed:
            return "fine_tuned"
        if self.baseline.passed > self.fine_tuned.passed:
            return "baseline"
        return "tie"


class ComparisonReport(BaseModel):
    """The full Demo 3 result across all prompts."""

    model_config = ConfigDict(extra="forbid", protected_namespaces=())

    baseline_model: str
    fine_tuned_model: str
    comparisons: list[PromptComparison] = Field(default_factory=list)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def baseline_total(self) -> int:
        return sum(c.baseline.passed for c in self.comparisons)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def fine_tuned_total(self) -> int:
        return sum(c.fine_tuned.passed for c in self.comparisons)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def max_total(self) -> int:
        return sum(c.baseline.total for c in self.comparisons)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def summary(self) -> str:
        return (
            f"fine-tuned {self.fine_tuned_total}/{self.max_total} vs "
            f"baseline {self.baseline_total}/{self.max_total}"
        )

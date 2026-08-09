"""Schemas for the model catalog, benchmarks, and leaderboard.

Metric names and directions mirror the Foundry leaderboard exactly as it appears
in the *Explore and compare models* guide (§7–§8). Getting the direction right
matters: two of the four axes are "lower is better", which is easy to invert.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

#: The leaderboard's four axes, with the direction that counts as "better".
#: Sourced verbatim from the guide's axis labels.
METRIC_DIRECTION: dict[str, Literal["higher", "lower"]] = {
    "quality_index": "higher",  # "Quality index; Higher is better"
    "safety_attack_success_rate": "lower",  # "Attack success rate; Lower is better"
    "throughput_tps": "higher",  # "Output Tokens per Second; Higher is better"
    "benchmark_cost_usd": "lower",  # "USD to benchmark quality datasets; Lower is better"
}

METRIC_LABEL: dict[str, str] = {
    "quality_index": "Quality index",
    "safety_attack_success_rate": "Safety",
    "throughput_tps": "Throughput (tokens/sec)",
    "benchmark_cost_usd": "Benchmark cost",
}

METRIC_SUBLABEL: dict[str, str] = {
    "quality_index": "Quality index; Higher is better",
    "safety_attack_success_rate": "Attack success rate; Lower is better",
    "throughput_tps": "Output Tokens per Second; Higher is better",
    "benchmark_cost_usd": "USD to benchmark quality datasets; Lower is better",
}


class Benchmarks(BaseModel):
    """The four public-benchmark metrics Foundry reports per model."""

    model_config = ConfigDict(extra="forbid")

    quality_index: float = Field(ge=0, le=1)
    safety_attack_success_rate: float = Field(ge=0, le=100, description="percent")
    throughput_tps: float = Field(ge=0)
    benchmark_cost_usd: float = Field(ge=0)


class ContextWindow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    input_tokens: int = Field(gt=0)
    output_tokens: int = Field(gt=0)


class ModelCard(BaseModel):
    """A model catalog entry."""

    model_config = ConfigDict(extra="forbid", protected_namespaces=())

    name: str
    version: str
    provider: str = "Azure OpenAI"
    description: str = ""
    lifecycle: str = "Generally Available"
    input_types: list[str] = Field(default_factory=lambda: ["text"])
    output_types: list[str] = Field(default_factory=lambda: ["text"])
    context: ContextWindow
    supports_fine_tuning: bool = False
    supports_tool_calling: bool = True
    supports_streaming: bool = True
    training_date: str = ""
    benchmarks: Benchmarks | None = None


class LeaderboardRow(BaseModel):
    """One row of the leaderboard comparison table."""

    model_config = ConfigDict(extra="forbid", protected_namespaces=())

    model_name: str
    quality_index: float
    safety_attack_success_rate: float
    throughput_tps: float
    benchmark_cost_usd: float

    def metric(self, key: str) -> float:
        return getattr(self, key)


class Leaderboard(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rows: list[LeaderboardRow]

    def ranked_by(self, metric: str) -> list[LeaderboardRow]:
        """Rank rows best-first for the given metric, honouring its direction."""
        if metric not in METRIC_DIRECTION:
            raise ValueError(f"unknown metric {metric!r}; expected one of {list(METRIC_DIRECTION)}")
        descending = METRIC_DIRECTION[metric] == "higher"
        return sorted(self.rows, key=lambda r: r.metric(metric), reverse=descending)

    def winner(self, metric: str) -> LeaderboardRow:
        return self.ranked_by(metric)[0]


class ComparisonRow(BaseModel):
    """One attribute compared across two models, with the winner marked."""

    model_config = ConfigDict(extra="forbid")

    attribute: str
    values: dict[str, str | float | bool | None]
    winner: str | None = None


class ModelComparison(BaseModel):
    """Side-by-side comparison of two or more models (guide §8, 'Compare models')."""

    model_config = ConfigDict(extra="forbid", protected_namespaces=())

    model_names: list[str] = Field(min_length=2)
    rows: list[ComparisonRow]

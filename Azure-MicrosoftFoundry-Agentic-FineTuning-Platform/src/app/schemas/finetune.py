"""Schemas for supervised fine-tuning jobs.

Mirrors the job configuration and status ladder shown in *Fine-tune a language
model* §8 and its Details/Monitor/Logs tabs.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, computed_field


class JobStatus(StrEnum):
    """Status ladder as reported by the Foundry fine-tuning job list."""

    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"

    @property
    def is_terminal(self) -> bool:
        return self in {JobStatus.SUCCEEDED, JobStatus.FAILED, JobStatus.CANCELLED}


class Hyperparameters(BaseModel):
    """Pinned explicitly.

    The guide leaves these at API defaults and never displays them, so a rerun is
    not reproducible. We pin them and record that as a deliberate divergence.
    """

    model_config = ConfigDict(extra="forbid")

    n_epochs: int = Field(default=2, ge=1, le=50)
    batch_size: int = Field(default=1, ge=1)
    learning_rate_multiplier: float = Field(default=1.0, gt=0)
    seed: int = 42


class FineTuneJobConfig(BaseModel):
    """The submit-time configuration (guide §8 step 4)."""

    model_config = ConfigDict(extra="forbid", protected_namespaces=())

    base_model: str = "gpt-4.1"
    base_model_version: str = "2025-04-14"
    customization_method: Literal["Supervised", "DPO", "Reinforcement"] = "Supervised"
    training_type: Literal["Developer", "Global", "Regional"] = "Developer"
    training_file: str = "travel-finetune-hotel.jsonl"
    validation_file: str | None = None
    suffix: str = "ft-travel"
    auto_deploy: bool = True
    deployment_type: Literal["Developer", "GlobalStandard", "Standard"] = "Developer"
    hyperparameters: Hyperparameters = Field(default_factory=Hyperparameters)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def qualified_base_model(self) -> str:
        return f"{self.base_model}-{self.base_model_version}"


class JobLogEntry(BaseModel):
    """One row of the job's Logs tab."""

    model_config = ConfigDict(extra="forbid")

    timestamp: datetime | None = None
    status: str = "info"
    type: Literal["message", "metrics"] = "message"
    message: str
    step: int | None = None
    training_loss: float | None = None


class Checkpoint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    step: int
    created_at: datetime | None = None
    metrics: dict[str, float] = Field(default_factory=dict)


class JobMetrics(BaseModel):
    """Metrics surfaced on the job Details tab."""

    model_config = ConfigDict(extra="forbid")

    final_train_loss: float | None = None
    final_train_mean_token_accuracy: float | None = None
    trained_tokens: int | None = None
    total_steps: int | None = None


class FineTuneJob(BaseModel):
    """A fine-tuning job and everything the portal shows about it."""

    model_config = ConfigDict(extra="forbid", protected_namespaces=())

    id: str
    name: str = ""
    status: JobStatus = JobStatus.QUEUED
    config: FineTuneJobConfig = Field(default_factory=FineTuneJobConfig)
    created_at: datetime | None = None
    finished_at: datetime | None = None
    duration_seconds: int | None = None
    metrics: JobMetrics = Field(default_factory=JobMetrics)
    fine_tuned_model: str | None = None
    deployment_name: str | None = None
    deployment_status: str | None = None
    logs: list[JobLogEntry] = Field(default_factory=list)
    checkpoints: list[Checkpoint] = Field(default_factory=list)
    error: str | None = None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def progress_pct(self) -> float:
        """Rough completion percentage, for the UI progress bar."""
        if self.status is JobStatus.SUCCEEDED:
            return 100.0
        if self.status in {JobStatus.FAILED, JobStatus.CANCELLED}:
            return 0.0
        total = self.metrics.total_steps or 100
        done = max((e.step or 0) for e in self.logs) if self.logs else 0
        return round(min(done / total, 0.99) * 100, 1)


class TrainingCostEstimate(BaseModel):
    """Cost projection using Microsoft's documented SFT formula.

        price = training_tokens x epochs x price_per_token

    ``training_tokens`` is the **per-epoch** token count, matching the formula.
    The job log's "Training tokens billed" figure is the *product* of the two
    (per-epoch x epochs), so pass that via ``billed_tokens`` instead — supplying
    it to ``training_tokens`` would double-count the epochs.

    Cross-check against the lab: 8,000 tokens/epoch x 2 epochs x $2/1M global
    = $0.032, exactly the total the guide reports. Developer tier halves it.
    """

    model_config = ConfigDict(extra="forbid")

    training_tokens: int = Field(gt=0, description="tokens per epoch")
    epochs: int = Field(gt=0)
    price_per_1m_tokens_usd: float = Field(gt=0)
    training_type: str = "Developer"

    @classmethod
    def from_billed_tokens(
        cls,
        billed_tokens: int,
        epochs: int,
        price_per_1m_tokens_usd: float,
        training_type: str = "Developer",
    ) -> TrainingCostEstimate:
        """Build from the job log's already-multiplied 'tokens billed' figure."""
        return cls(
            training_tokens=max(billed_tokens // max(epochs, 1), 1),
            epochs=epochs,
            price_per_1m_tokens_usd=price_per_1m_tokens_usd,
            training_type=training_type,
        )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def billed_tokens(self) -> int:
        return self.training_tokens * self.epochs

    @computed_field  # type: ignore[prop-decorator]
    @property
    def effective_rate_per_1m_usd(self) -> float:
        rate = self.price_per_1m_tokens_usd
        if self.training_type == "Developer":
            rate *= 0.5  # documented 50% discount from global training
        return rate

    @computed_field  # type: ignore[prop-decorator]
    @property
    def estimated_usd(self) -> float:
        return round(self.billed_tokens / 1_000_000 * self.effective_rate_per_1m_usd, 6)

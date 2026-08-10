"""The Pydantic graph state passed between orchestrator nodes.

Every field that crosses a node boundary is typed. The state is the only channel between
agents — nodes never reach into AWS clients directly, they call allowlisted MCP tools and
write their findings here.

`approval_token` is the one field with teeth: `start_finetune_job` refuses to execute
unless it holds the literal approval token. It is populated by a human typing it, never by
an agent, and never defaulted.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

NodeName = Literal["dataset_prep", "finetune_supervisor", "evaluation", "inference"]

NODE_SEQUENCE: tuple[NodeName, ...] = (
    "dataset_prep",
    "finetune_supervisor",
    "evaluation",
    "inference",
)


class DatasetFacts(BaseModel):
    model_config = ConfigDict(extra="forbid")

    record_count: int
    train_count: int
    validation_count: int
    invalid_line_numbers: list[int] = Field(default_factory=list)
    estimated_training_tokens: int


class CostFacts(BaseModel):
    model_config = ConfigDict(extra="forbid")

    training_cost_usd: float
    storage_cost_usd_per_month: float
    one_time_cost_usd: float


class JobFacts(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_arn: str | None = None
    status: str | None = None
    validation_status: str | None = None
    training_status: str | None = None
    output_model_arn: str | None = None
    failure_message: str | None = None


class EvalFacts(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scored: int = 0
    schema_valid: int = 0
    rule_compliant: int = 0
    notes: list[str] = Field(default_factory=list)


class GraphState(BaseModel):
    """State threaded through the orchestrator.

    `extra="forbid"` so a node cannot smuggle an untyped field past the boundary.
    """

    model_config = ConfigDict(extra="forbid")

    scenario_id: str
    dry_run: bool = True

    # Never defaulted and never set by an agent. Absent means no billable action may run.
    approval_token: str | None = None

    dataset: DatasetFacts | None = None
    cost: CostFacts | None = None
    job: JobFacts | None = None
    evaluation: EvalFacts | None = None

    visited: list[NodeName] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)

    def record_visit(self, node: NodeName) -> None:
        self.visited.append(node)

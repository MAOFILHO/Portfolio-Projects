"""MCP tools for dataset inspection. All read-only.

Nothing here writes to S3 or AWS. `split_dataset` writes only to the local
`artifacts/{scenario}/splits/` directory, which the deterministic pipeline already owns —
it produces no billable resource and no remote state.

Every tool takes and returns a Pydantic model, so no untyped dict crosses the agent
boundary.
"""

import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from bedrock_platform.aws.cost_estimator import estimate_cost
from bedrock_platform.config.scenario_config import ScenarioConfig
from bedrock_platform.config.scenario_loader import load_scenarios
from bedrock_platform.data.splitter import split_records

DATASET_TOOLS: tuple[str, ...] = (
    "validate_dataset",
    "split_dataset",
    "estimate_training_cost",
)

REPO_ROOT = Path(__file__).resolve().parents[3]
# Bedrock's conversation format bills roughly per token; 4 chars/token is the standard
# rough conversion used throughout COSTS.md. Good enough for a pre-flight estimate,
# never used to bill anything.
CHARS_PER_TOKEN = 4


class ValidateDatasetInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scenario_id: str


class ValidateDatasetOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scenario_id: str
    record_count: int
    invalid_line_numbers: list[int]
    schema_version_mismatches: list[int]
    estimated_training_tokens: int


class SplitDatasetInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scenario_id: str


class SplitDatasetOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scenario_id: str
    train_count: int
    validation_count: int
    train_path: str
    validation_path: str


class EstimateCostInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scenario_id: str
    training_tokens: int


class EstimateCostOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scenario_id: str
    base_model_id: str
    training_cost_usd: float
    storage_cost_usd_per_month: float
    one_time_cost_usd: float


def _scenario(scenario_id: str) -> ScenarioConfig:
    for scenario in load_scenarios():
        if scenario.id == scenario_id:
            return scenario
    raise ValueError(f"unknown scenario id {scenario_id!r}")


def _records(scenario: ScenarioConfig) -> list[str]:
    return [line for line in scenario.dataset_path.read_text().splitlines() if line.strip()]


def validate_dataset(payload: ValidateDatasetInput) -> ValidateDatasetOutput:
    scenario = _scenario(payload.scenario_id)
    records = _records(scenario)

    invalid: list[int] = []
    mismatched: list[int] = []
    total_chars = 0

    for index, line in enumerate(records, start=1):
        total_chars += len(line)
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            invalid.append(index)
            continue
        if record.get("schemaVersion") != "bedrock-conversation-2024":
            mismatched.append(index)
        if not record.get("messages"):
            invalid.append(index)

    return ValidateDatasetOutput(
        scenario_id=scenario.id,
        record_count=len(records),
        invalid_line_numbers=invalid,
        schema_version_mismatches=mismatched,
        estimated_training_tokens=(total_chars // CHARS_PER_TOKEN) * scenario.epochs,
    )


def split_dataset(payload: SplitDatasetInput) -> SplitDatasetOutput:
    scenario = _scenario(payload.scenario_id)
    train, validation = split_records(_records(scenario), scenario.validation_split)

    split_dir = REPO_ROOT / "artifacts" / scenario.id / "splits"
    split_dir.mkdir(parents=True, exist_ok=True)
    train_path = split_dir / "train.jsonl"
    validation_path = split_dir / "validation.jsonl"
    train_path.write_text("\n".join(train) + "\n")
    validation_path.write_text("\n".join(validation) + "\n")

    return SplitDatasetOutput(
        scenario_id=scenario.id,
        train_count=len(train),
        validation_count=len(validation),
        train_path=str(train_path),
        validation_path=str(validation_path),
    )


def estimate_training_cost(payload: EstimateCostInput) -> EstimateCostOutput:
    """Live Price List API lookup. Read-only, and the source of the number a human sees
    before typing an approval token."""
    scenario = _scenario(payload.scenario_id)
    estimate = estimate_cost(
        scenario_id=scenario.id,
        base_model_id=scenario.base_model_id,
        training_tokens=payload.training_tokens,
        input_tokens=0,
        output_tokens=0,
    )
    return EstimateCostOutput(
        scenario_id=scenario.id,
        base_model_id=scenario.base_model_id,
        training_cost_usd=estimate.training_cost_usd,
        storage_cost_usd_per_month=estimate.storage_cost_usd_per_month,
        one_time_cost_usd=estimate.training_cost_usd,
    )

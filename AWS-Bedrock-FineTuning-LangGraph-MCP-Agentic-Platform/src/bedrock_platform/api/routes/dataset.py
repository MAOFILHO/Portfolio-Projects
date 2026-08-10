import json

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict

from bedrock_platform.api.deps import get_enabled_scenario
from bedrock_platform.config.scenario_config import ScenarioConfig
from bedrock_platform.models.dataset_record import ConversationRecord

router = APIRouter()

PREVIEW_RECORD_COUNT = 3


class DatasetInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scenario_id: str
    dataset_path: str
    record_count: int
    system_prompt: str
    preview_records: list[ConversationRecord]


@router.get("/dataset/{scenario_id}", response_model=DatasetInfo)
def inspect_dataset(scenario: ScenarioConfig = Depends(get_enabled_scenario)) -> DatasetInfo:
    lines = [line for line in scenario.dataset_path.read_text().splitlines() if line.strip()]
    records = [ConversationRecord.model_validate(json.loads(line)) for line in lines]

    return DatasetInfo(
        scenario_id=scenario.id,
        dataset_path=str(scenario.dataset_path),
        record_count=len(records),
        system_prompt=scenario.system_prompt,
        preview_records=records[:PREVIEW_RECORD_COUNT],
    )

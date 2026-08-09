"""Unit tests for the selectable dataset catalog (app.schemas.dataset) and the
MCP tools/routes built on top of it.

Covers the 7 datasets converted from AWS Bedrock's Converse format by
data/convert_bedrock_datasets.py, plus the lab's own travel-finetune-hotel.jsonl
which must remain the default and be unaffected by any of this.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.mcp_clients.registry import call_tool
from app.schemas.dataset import DATASET_REGISTRY, dataset_relative_path, get_dataset


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


def test_registry_has_8_datasets_travel_first():
    assert len(DATASET_REGISTRY) == 8
    assert DATASET_REGISTRY[0].id == "travel-finetune-hotel"
    assert DATASET_REGISTRY[0].subdir == ""


def test_converted_datasets_live_under_converted_subdir():
    for info in DATASET_REGISTRY[1:]:
        assert info.subdir == "converted"


def test_get_dataset_unknown_id_raises():
    with pytest.raises(KeyError):
        get_dataset("not-a-real-dataset")


def test_dataset_relative_path_matches_subdir():
    assert dataset_relative_path("travel-finetune-hotel") == "travel-finetune-hotel.jsonl"
    assert dataset_relative_path("gardening-lessons") == "converted/gardening_lessons.jsonl"


@pytest.mark.asyncio
async def test_list_datasets_tool_returns_all_8():
    result = await call_tool("list_datasets")
    assert result["count"] == 8
    ids = {d["id"] for d in result["datasets"]}
    assert "travel-finetune-hotel" in ids
    assert "banking-assistant" in ids


@pytest.mark.asyncio
@pytest.mark.parametrize("dataset_id", [d.id for d in DATASET_REGISTRY])
async def test_every_catalog_dataset_validates_clean(dataset_id: str):
    result = await call_tool("validate_jsonl", {"dataset_id": dataset_id})
    assert result["is_valid"] is True, f"{dataset_id}: {result.get('errors')}"
    assert result["valid_rows"] == result["total_lines"]
    assert result["valid_rows"] > 0


@pytest.mark.asyncio
async def test_upload_by_dataset_id_matches_file(dataset_id="ecommerce-product-copy"):
    result = await call_tool("upload_training_file", {"dataset_id": dataset_id})
    assert result["file_name"] == "ecommerce_product_copy.jsonl"
    assert result["rows"] > 0


@pytest.mark.asyncio
async def test_travel_dataset_cost_estimate_unaffected_by_dataset_id():
    # The travel dataset must keep using the lab's real recorded 16,000-token
    # figure, not the char/4 heuristic, even when addressed by dataset_id.
    result = await call_tool(
        "estimate_training_cost",
        {"dataset_id": "travel-finetune-hotel", "training_type": "Developer"},
    )
    assert result["estimated_usd"] == pytest.approx(0.016, abs=0.001)
    assert "heuristic" not in result["note"].lower()


@pytest.mark.asyncio
async def test_non_travel_dataset_cost_estimate_uses_heuristic_and_labels_it():
    result = await call_tool(
        "estimate_training_cost", {"dataset_id": "it-helpdesk-l1", "training_type": "Developer"}
    )
    assert result["estimated_usd"] > 0
    assert "heuristic" in result["note"].lower()


def test_router_list_datasets(client: TestClient):
    res = client.get("/finetune/datasets")
    assert res.status_code == 200
    assert res.json()["count"] == 8


def test_router_validate_by_dataset_id(client: TestClient):
    res = client.get("/finetune/validate", params={"dataset_id": "banking-assistant"})
    assert res.status_code == 200
    body = res.json()
    assert body["is_valid"] is True
    assert body["file_name"] == "banking_assistant.jsonl"


def test_router_estimate_by_dataset_id(client: TestClient):
    res = client.post("/finetune/estimate", params={"dataset_id": "pharma-adverse-event-triage"})
    assert res.status_code == 200
    assert res.json()["estimated_usd"] > 0


def test_router_validate_default_still_travel_dataset(client: TestClient):
    # No dataset_id / path -> must still be the lab's own file, unaffected.
    res = client.get("/finetune/validate")
    assert res.status_code == 200
    body = res.json()
    assert body["file_name"] == "travel-finetune-hotel.jsonl"
    assert body["valid_rows"] == 10

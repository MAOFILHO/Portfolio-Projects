"""DynamoDB-backed LangGraph state persistence -- `ADR-005`: adopt `langgraph-checkpoint-aws`'s
`DynamoDBSaver`, keyed on the Connect contact ID (LangGraph's `thread_id`), rather than hand-writing a
`BaseCheckpointSaver`.

**No real DynamoDB table is created by this module, or anywhere in Phase 5** (`docs/phase5/BUILD-PLAN.md`
§2) -- `build_checkpointer` assumes a table already exists (Phase 8's provisioning job) and simply wraps
`DynamoDBSaver`'s constructor with this project's region convention (`config/settings.DEFAULT_REGION`,
never a hardcoded literal). `create_checkpoint_table` exists only for tests, against a moto-mocked
DynamoDB -- mirroring `knowledge/ingest.py`'s `DynamoVectorStore.ensure_table` pattern for the same reason:
tests need a table to exist somewhere, and moto is the zero-cost way to get one.
"""

from __future__ import annotations

from typing import Any

import boto3
from langgraph_checkpoint_aws import DynamoDBSaver

from fnol_voice_agent.config.settings import DEFAULT_REGION

# The single-table key schema langgraph-checkpoint-aws's DynamoDBSaver itself uses (confirmed by reading
# its unified_repository.py, not assumed): partition key "PK", sort key "SK", both String.
_PARTITION_KEY = "PK"
_SORT_KEY = "SK"


def build_checkpointer(table_name: str, *, region: str = DEFAULT_REGION) -> DynamoDBSaver:
    """Real checkpointer wiring. Requires a table that already exists -- this function never creates one
    (Phase 8's job, not this one's)."""
    return DynamoDBSaver(table_name=table_name, region_name=region)


def create_checkpoint_table(client: Any, table_name: str) -> None:
    """Test-only: creates the checkpoint table's schema against a moto-mocked DynamoDB (or, in principle,
    a real one -- but this project never calls this outside `mock_aws()`, per the module docstring).
    """
    client.create_table(
        TableName=table_name,
        KeySchema=[
            {"AttributeName": _PARTITION_KEY, "KeyType": "HASH"},
            {"AttributeName": _SORT_KEY, "KeyType": "RANGE"},
        ],
        AttributeDefinitions=[
            {"AttributeName": _PARTITION_KEY, "AttributeType": "S"},
            {"AttributeName": _SORT_KEY, "AttributeType": "S"},
        ],
        BillingMode="PAY_PER_REQUEST",
    )


def build_test_checkpointer(table_name: str, *, region: str = DEFAULT_REGION) -> DynamoDBSaver:
    """Test-only convenience: creates the table (via `create_checkpoint_table`) against whatever DynamoDB
    endpoint boto3 currently resolves to -- a moto-mocked one inside `mock_aws()`, never real. Callers are
    responsible for wrapping this in `mock_aws()`; this function does not check that they did."""
    client = boto3.client("dynamodb", region_name=region)
    create_checkpoint_table(client, table_name)
    return build_checkpointer(table_name, region=region)

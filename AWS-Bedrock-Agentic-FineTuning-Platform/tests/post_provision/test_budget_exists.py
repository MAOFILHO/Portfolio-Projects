import os

import boto3
import pytest


def test_budget_exists_with_approved_limit() -> None:
    suffix = os.environ.get("PROJECT_SUFFIX")
    limit = os.environ.get("BUDGET_LIMIT_USD")
    if not suffix or not limit:
        pytest.skip("PROJECT_SUFFIX or BUDGET_LIMIT_USD not set")

    sts = boto3.client("sts", region_name="us-east-1")
    account_id = sts.get_caller_identity()["Account"]

    client = boto3.client("budgets", region_name="us-east-1")
    response = client.describe_budget(
        AccountId=account_id, BudgetName=f"bedrock-platform-{suffix}-monthly"
    )
    budget = response["Budget"]
    assert budget["BudgetLimit"]["Unit"] == "USD"
    assert float(budget["BudgetLimit"]["Amount"]) == pytest.approx(float(limit))

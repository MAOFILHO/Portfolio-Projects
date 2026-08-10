"""The detection path of scripts/verify_no_billable.py.

Written because the script first ran against an already-empty account, so its failure
branch had never executed. A checker only ever observed returning "all clear" is not
evidence that it can catch anything — the same defect that let verify_empty.py falsely
certify a clean teardown, and let teardown.py hide a KeyError behind an empty account.
"""

import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from verify_no_billable import find_billable_resources  # noqa: E402

BUCKET = "bedrock-platform-test-suffix-data-us-west-2"


class FakeBedrock:
    def __init__(
        self,
        deployments: list[dict[str, Any]] | None = None,
        models: list[dict[str, Any]] | None = None,
        throughputs: list[dict[str, Any]] | None = None,
    ) -> None:
        self._deployments = deployments or []
        self._models = models or []
        self._throughputs = throughputs or []

    def list_custom_model_deployments(self) -> dict[str, Any]:
        return {"modelDeploymentSummaries": self._deployments}

    def list_custom_models(self) -> dict[str, Any]:
        return {"modelSummaries": self._models}

    def list_provisioned_model_throughputs(self) -> dict[str, Any]:
        return {"provisionedModelSummaries": self._throughputs}


class FakeS3:
    def __init__(self, key_count: int = 0) -> None:
        self._key_count = key_count

    def list_objects_v2(self, **_kwargs: Any) -> dict[str, Any]:
        return {"KeyCount": self._key_count}


def test_empty_account_reports_no_problems() -> None:
    problems = find_billable_resources(FakeBedrock(), FakeS3(), BUCKET, "us-west-2")
    assert problems == []


def test_surviving_deployment_is_detected() -> None:
    bedrock = FakeBedrock(
        deployments=[
            {"customModelDeploymentName": "marco-demo01-pharma-deploy", "status": "Active"}
        ]
    )
    problems = find_billable_resources(bedrock, FakeS3(), BUCKET, "us-west-2")
    assert len(problems) == 1
    assert "marco-demo01-pharma-deploy" in problems[0]


def test_surviving_custom_model_is_detected() -> None:
    """The one that actually costs money — $1.95/model/month until deleted."""
    bedrock = FakeBedrock(models=[{"modelName": "marco-demo01-pharma-llama-ft"}])
    problems = find_billable_resources(bedrock, FakeS3(), BUCKET, "us-west-2")
    assert len(problems) == 1
    assert "marco-demo01-pharma-llama-ft" in problems[0]


def test_provisioned_throughput_is_detected() -> None:
    """Should be impossible to create from this project, so its presence means something
    outside the project made one — at $60.50/hr, that must not pass silently."""
    bedrock = FakeBedrock(throughputs=[{"provisionedModelName": "rogue-throughput"}])
    problems = find_billable_resources(bedrock, FakeS3(), BUCKET, "us-west-2")
    assert len(problems) == 1
    assert "rogue-throughput" in problems[0]


def test_leftover_s3_objects_are_detected() -> None:
    problems = find_billable_resources(FakeBedrock(), FakeS3(key_count=3), BUCKET, "us-west-2")
    assert len(problems) == 1
    assert BUCKET in problems[0]


def test_every_surviving_resource_is_reported_not_just_the_first() -> None:
    """Reporting only the first would leave a teardown looking almost-clean."""
    bedrock = FakeBedrock(
        deployments=[{"customModelDeploymentName": "d1", "status": "Active"}],
        models=[{"modelName": "m1"}, {"modelName": "m2"}],
        throughputs=[{"provisionedModelName": "pt1"}],
    )
    problems = find_billable_resources(bedrock, FakeS3(key_count=7), BUCKET, "us-west-2")
    assert len(problems) == 5

import time
from typing import Any

import boto3

MAX_IN_PROGRESS_DEPLOYMENTS = 2
IN_PROGRESS_STATUSES = {"Creating"}


class DeploymentQuotaTimeoutError(Exception):
    """Raised when no deployment slot frees up within the polling budget."""


class DeploymentClient:
    def __init__(self, session: boto3.Session | None = None) -> None:
        self._session = session or boto3.Session()
        self._bedrock = self._session.client("bedrock")

    def list_custom_model_deployments(self) -> list[dict[str, Any]]:
        deployments: list[dict[str, Any]] = []
        paginator = self._bedrock.get_paginator("list_custom_model_deployments")
        for page in paginator.paginate():
            deployments.extend(
                dict(summary) for summary in page.get("modelDeploymentSummaries", [])
            )
        return deployments

    def _in_progress_count(self) -> int:
        return sum(
            1
            for d in self.list_custom_model_deployments()
            if d.get("status") in IN_PROGRESS_STATUSES
        )

    def _wait_for_free_slot(
        self, poll_interval_seconds: int = 30, max_wait_seconds: int = 3600
    ) -> None:
        waited = 0
        while self._in_progress_count() >= MAX_IN_PROGRESS_DEPLOYMENTS:
            if waited >= max_wait_seconds:
                raise DeploymentQuotaTimeoutError(
                    f"No deployment slot freed up within {max_wait_seconds}s "
                    f"(quota: {MAX_IN_PROGRESS_DEPLOYMENTS} in-progress deployments)."
                )
            time.sleep(poll_interval_seconds)
            waited += poll_interval_seconds

    def create_custom_model_deployment(
        self, deployment_name: str, custom_model_arn: str
    ) -> dict[str, Any]:
        self._wait_for_free_slot()
        return dict(
            self._bedrock.create_custom_model_deployment(
                modelDeploymentName=deployment_name,
                modelArn=custom_model_arn,
            )
        )

    def get_custom_model_deployment(self, deployment_arn: str) -> dict[str, Any]:
        return dict(
            self._bedrock.get_custom_model_deployment(
                customModelDeploymentIdentifier=deployment_arn
            )
        )

    def delete_custom_model_deployment(self, deployment_arn: str) -> None:
        self._bedrock.delete_custom_model_deployment(customModelDeploymentIdentifier=deployment_arn)

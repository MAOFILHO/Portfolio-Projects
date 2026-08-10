from typing import Any

import boto3

from bedrock_platform.aws.guards import assert_not_provisioned_throughput

APPROVAL_TOKEN = "APPROVE"


class RetrainRefusedError(Exception):
    """Raised when a completed custom model already exists and retraining wasn't approved."""


class FinetuneClient:
    def __init__(self, project_suffix: str, session: boto3.Session | None = None) -> None:
        self.project_suffix = project_suffix
        self._session = session or boto3.Session()
        self._bedrock = self._session.client("bedrock")

    def job_name(self, scenario_id: str) -> str:
        return f"{self.project_suffix}-{scenario_id}-ft"

    @staticmethod
    def _normalise(name: str) -> str:
        """Bedrock resource names use hyphens where scenario ids use underscores
        (`it_helpdesk` -> `it-helpdesk`), so compare on a single separator."""
        return name.replace("_", "-").lower()

    def scenario_model_prefix(self, scenario_id: str) -> str:
        return self._normalise(f"{self.project_suffix}-{scenario_id}")

    def find_custom_models(self, scenario_id: str) -> list[dict[str, Any]]:
        """All custom models belonging to a scenario, newest first.

        Resolution is by prefix rather than by an exact `job_name()` match. Bedrock
        reserves job and custom-model names permanently and they cannot be renamed, so a
        scenario that took several attempts — or that moved base model, as this project
        did from Nova to Llama — has its live model under a name the canonical pattern no
        longer reproduces. Matching exactly would report "no model exists" while three
        `Active` models sat in the account.

        This is discovery of existing resources, not rename-on-collision: creation still
        uses the single deterministic `job_name()`.
        """
        prefix = self.scenario_model_prefix(scenario_id)
        matches = [
            model
            for model in self.list_custom_models()
            if self._normalise(model["modelName"]).startswith(prefix)
        ]
        return sorted(matches, key=lambda m: m.get("creationTime", 0), reverse=True)

    def list_model_customization_jobs(self) -> list[dict[str, Any]]:
        jobs: list[dict[str, Any]] = []
        paginator = self._bedrock.get_paginator("list_model_customization_jobs")
        for page in paginator.paginate():
            jobs.extend(dict(summary) for summary in page.get("modelCustomizationJobSummaries", []))
        return jobs

    def find_jobs(self, scenario_id: str) -> list[dict[str, Any]]:
        """All customization jobs belonging to a scenario, newest first.

        Same reasoning as `find_custom_models`: Bedrock reserves job names permanently, so
        a scenario that took several attempts — or that changed base model — has its real
        job under a name the canonical `job_name()` no longer reproduces. Looking up the
        canonical name returns ResourceNotFound, which the UI surfaces as status
        "Unknown" for a job that in fact completed.
        """
        prefix = self.scenario_model_prefix(scenario_id)
        matches = [
            job
            for job in self.list_model_customization_jobs()
            if self._normalise(job["jobName"]).startswith(prefix)
        ]
        return sorted(matches, key=lambda j: j.get("creationTime", 0), reverse=True)

    def resolve_job_identifier(self, scenario_id: str) -> str:
        """The job identifier the UI and pollers should track for a scenario.

        Prefers the newest real job over the canonical name, so a scenario works without
        anyone having hand-written an active_job.json override.
        """
        jobs = self.find_jobs(scenario_id)
        if jobs:
            return str(jobs[0]["jobArn"])
        return self.job_name(scenario_id)

    def _completed_model_exists(self, scenario_id: str) -> bool:
        return bool(self.find_custom_models(scenario_id))

    def create_model_customization_job(
        self,
        scenario_id: str,
        base_model_id: str,
        role_arn: str,
        training_data_s3_uri: str,
        validation_data_s3_uri: str,
        output_s3_uri: str,
        epochs: int,
        force_retrain: bool = False,
        approval_token: str | None = None,
    ) -> dict[str, Any]:
        assert_not_provisioned_throughput(base_model_id)

        if self._completed_model_exists(scenario_id) and (
            not force_retrain or approval_token != APPROVAL_TOKEN
        ):
            raise RetrainRefusedError(
                f"A completed custom model already exists for scenario {scenario_id!r}. "
                "Pass force_retrain=True with a valid typed approval token to retrain."
            )

        job_name = self.job_name(scenario_id)
        custom_model_name = job_name

        # boto3-stubs returns a TypedDict, which is invariant and so not assignable to
        # dict[str, Any]. Convert explicitly rather than widening the public signature.
        return dict(
            self._bedrock.create_model_customization_job(
                jobName=job_name,
                customModelName=custom_model_name,
                roleArn=role_arn,
                baseModelIdentifier=base_model_id,
                trainingDataConfig={"s3Uri": training_data_s3_uri},
                validationDataConfig={
                    "validators": [{"s3Uri": validation_data_s3_uri}],
                },
                outputDataConfig={"s3Uri": output_s3_uri},
                hyperParameters={"epochCount": str(epochs)},
            )
        )

    def get_model_customization_job(self, job_identifier: str) -> dict[str, Any]:
        return dict(self._bedrock.get_model_customization_job(jobIdentifier=job_identifier))

    def get_custom_model(self, model_identifier: str) -> dict[str, Any]:
        return dict(self._bedrock.get_custom_model(modelIdentifier=model_identifier))

    def job_arn_for_model(self, model_identifier: str) -> str:
        """The customization job that produced a model. Recorded in run artifacts so the
        run is traceable back to its job on both the train and --skip-training paths,
        without reconstructing a job name Bedrock may have reserved for an earlier attempt.
        """
        return str(self.get_custom_model(model_identifier)["jobArn"])

    def list_custom_models(self) -> list[dict[str, Any]]:
        models: list[dict[str, Any]] = []
        paginator = self._bedrock.get_paginator("list_custom_models")
        for page in paginator.paginate():
            models.extend(dict(summary) for summary in page.get("modelSummaries", []))
        return models

    def delete_custom_model(self, model_identifier: str) -> None:
        self._bedrock.delete_custom_model(modelIdentifier=model_identifier)

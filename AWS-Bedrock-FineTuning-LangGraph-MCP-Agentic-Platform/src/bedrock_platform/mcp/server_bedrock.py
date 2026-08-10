"""MCP tools for Bedrock. One mutating tool, gated; everything else read-only.

What is deliberately **absent** matters more than what is present. There is no tool to
delete a model, create a deployment, modify IAM, change S3 lifecycle, or touch the budget.
Those are deterministic scripts run by humans (`scripts/teardown.py`, Terraform). An agent
cannot reach them because they are not in its vocabulary — see `allowlist.py` for the
second layer.

`start_finetune_job` is the single exception: the one action an agent can take that costs
money. It refuses unless a human-typed approval token reaches it through graph state.
"""

from typing import Any

from pydantic import BaseModel, ConfigDict

from bedrock_platform.aws.finetune_client import APPROVAL_TOKEN, FinetuneClient
from bedrock_platform.aws.inference_client import InferenceClient
from bedrock_platform.aws.naming import bedrock_role_arn, data_bucket_name
from bedrock_platform.aws.session import get_session
from bedrock_platform.config.scenario_config import ScenarioConfig
from bedrock_platform.config.scenario_loader import load_scenarios
from bedrock_platform.config.settings import Settings
from bedrock_platform.observability.langfuse_setup import record_generation_usage, trace_step

BEDROCK_TOOLS: tuple[str, ...] = (
    "start_finetune_job",
    "get_job_status",
    "read_training_metrics",
    "invoke_base_model",
    "invoke_tuned_model",
)


class ApprovalRequiredError(PermissionError):
    """Raised when a billable action is attempted without a valid human approval token."""


class StartFinetuneInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scenario_id: str
    # Threaded from GraphState. Never defaulted — an absent token must fail, not proceed.
    approval_token: str | None = None
    dry_run: bool = True


class StartFinetuneOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scenario_id: str
    job_arn: str | None
    dry_run: bool
    planned_job_name: str


class JobStatusInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_identifier: str


class JobStatusOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str
    validation_status: str | None
    training_status: str | None
    output_model_arn: str | None
    failure_message: str | None


class TrainingMetricsInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scenario_id: str
    job_identifier: str


class TrainingMetricsOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scenario_id: str
    training_loss: list[float]
    validation_loss: list[float]


class InvokeInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scenario_id: str
    prompt: str
    deployment_arn: str | None = None


class InvokeOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str
    input_tokens: int
    output_tokens: int
    latency_ms: float


def _scenario(scenario_id: str) -> ScenarioConfig:
    for scenario in load_scenarios():
        if scenario.id == scenario_id:
            return scenario
    raise ValueError(f"unknown scenario id {scenario_id!r}")


def start_finetune_job(payload: StartFinetuneInput) -> StartFinetuneOutput:
    """The only agent-reachable action that spends money.

    Two independent conditions must hold before a job is created: a valid approval token
    that only a human can supply, and dry_run explicitly turned off. Failing either
    returns a plan rather than a job.
    """
    settings = Settings()  # type: ignore[call-arg]  # values come from .env at runtime
    scenario = _scenario(payload.scenario_id)
    session = get_session()
    client = FinetuneClient(project_suffix=settings.project_suffix, session=session)
    planned_job_name = client.job_name(scenario.id)

    if payload.dry_run:
        return StartFinetuneOutput(
            scenario_id=scenario.id,
            job_arn=None,
            dry_run=True,
            planned_job_name=planned_job_name,
        )

    if payload.approval_token != APPROVAL_TOKEN:
        raise ApprovalRequiredError(
            f"start_finetune_job refused for scenario {scenario.id!r}: a valid typed "
            f"approval token is required before launching a billable fine-tuning job. "
            f"No agent may supply this token."
        )

    bucket = data_bucket_name(settings.project_suffix, settings.aws_region)
    response = client.create_model_customization_job(
        scenario_id=scenario.id,
        base_model_id=scenario.base_model_id,
        role_arn=bedrock_role_arn(session, settings.project_suffix),
        training_data_s3_uri=f"s3://{bucket}/training-data/{scenario.id}/train.jsonl",
        validation_data_s3_uri=f"s3://{bucket}/validation-data/{scenario.id}/validation.jsonl",
        output_s3_uri=f"s3://{bucket}/output/{scenario.id}/",
        epochs=scenario.epochs,
    )
    return StartFinetuneOutput(
        scenario_id=scenario.id,
        job_arn=response["jobArn"],
        dry_run=False,
        planned_job_name=planned_job_name,
    )


def get_job_status(payload: JobStatusInput) -> JobStatusOutput:
    settings = Settings()  # type: ignore[call-arg]  # values come from .env at runtime
    client = FinetuneClient(project_suffix=settings.project_suffix, session=get_session())
    job = client.get_model_customization_job(payload.job_identifier)
    details = job.get("statusDetails") or {}
    return JobStatusOutput(
        status=job["status"],
        validation_status=(details.get("validationDetails") or {}).get("status"),
        training_status=(details.get("trainingDetails") or {}).get("status"),
        output_model_arn=job.get("outputModelArn"),
        failure_message=job.get("failureMessage"),
    )


def read_training_metrics(payload: TrainingMetricsInput) -> TrainingMetricsOutput:
    """Reads the loss curves Bedrock writes to the output prefix. Read-only S3 GET."""
    settings = Settings()  # type: ignore[call-arg]  # values come from .env at runtime
    session = get_session()
    s3 = session.client("s3")
    bucket = data_bucket_name(settings.project_suffix, settings.aws_region)
    job_id = payload.job_identifier.rsplit("/", 1)[-1]
    prefix = f"output/{payload.scenario_id}/model-customization-job-{job_id}/"

    def _losses(key: str, column: str) -> list[float]:
        try:
            body = s3.get_object(Bucket=bucket, Key=prefix + key)["Body"].read().decode()
        except s3.exceptions.NoSuchKey:
            return []
        rows = [line for line in body.splitlines() if line.strip()]
        if not rows:
            return []
        header = rows[0].split(",")
        if column not in header:
            return []
        index = header.index(column)
        return [float(row.split(",")[index]) for row in rows[1:]]

    return TrainingMetricsOutput(
        scenario_id=payload.scenario_id,
        training_loss=_losses("training_artifacts/step_wise_training_metrics.csv", "training_loss"),
        validation_loss=_losses(
            "validation_artifacts/post_fine_tuning_validation/validation/validation_metrics.csv",
            "validation_loss",
        ),
    )


def _traced_invoke(
    name: str, model: str, scenario: ScenarioConfig, prompt: str, call: Any
) -> InvokeOutput:
    """Emits a `generation` observation carrying model name and token usage.

    Those two attributes are what let Langfuse attribute cost; a model call recorded as a
    plain tool span shows up with no model and no tokens, and is invisible to every cost
    dashboard.
    """
    with trace_step(
        name,
        as_type="generation",
        input=[
            {"role": "system", "content": scenario.system_prompt},
            {"role": "user", "content": prompt},
        ],
        model=model,
        scenario_id=scenario.id,
    ) as observation:
        result = call()
        record_generation_usage(
            observation,
            output=result.text,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
        )
        return InvokeOutput(**result.model_dump())


def invoke_base_model(payload: InvokeInput) -> InvokeOutput:
    scenario = _scenario(payload.scenario_id)
    client = InferenceClient(session=get_session())
    return _traced_invoke(
        "invoke-base-model",
        scenario.base_inference_model_id,
        scenario,
        payload.prompt,
        lambda: client.invoke_base_model(
            scenario.base_inference_model_id,
            scenario.system_prompt,
            payload.prompt,
            scenario.max_output_tokens,
        ),
    )


def invoke_tuned_model(payload: InvokeInput) -> InvokeOutput:
    if payload.deployment_arn is None:
        raise ValueError("invoke_tuned_model requires a deployment_arn")
    scenario = _scenario(payload.scenario_id)
    client = InferenceClient(session=get_session())
    return _traced_invoke(
        "invoke-tuned-model",
        # The custom model, not the deployment ARN — Langfuse prices by model name, and a
        # deployment ARN matches nothing in its pricing table.
        scenario.base_model_id,
        scenario,
        payload.prompt,
        lambda: client.invoke_tuned_model(
            payload.deployment_arn,
            scenario.system_prompt,
            payload.prompt,
            scenario.max_output_tokens,
        ),
    )

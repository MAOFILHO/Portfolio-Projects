import asyncio
import json
import time
from collections.abc import AsyncGenerator
from datetime import UTC, datetime

import boto3
from botocore.exceptions import ClientError
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict

from bedrock_platform.api.deps import get_boto_session, get_enabled_scenario, get_settings
from bedrock_platform.aws.finetune_client import APPROVAL_TOKEN, FinetuneClient, RetrainRefusedError
from bedrock_platform.aws.job_event_log import (
    append_event,
    read_active_job_override,
    read_events,
)
from bedrock_platform.aws.naming import bedrock_role_arn, data_bucket_name
from bedrock_platform.config.scenario_config import ScenarioConfig
from bedrock_platform.config.settings import Settings

router = APIRouter()

STATUS_POLL_SECONDS = 10
HEARTBEAT_INTERVAL_SECONDS = 240
STREAM_TAIL_POLL_SECONDS = 2
TERMINAL_STATUSES = {"Completed", "Failed", "Stopped"}

# Background pollers persist job status independently of any single browser
# connection, so history survives page refreshes and backend restarts.
# Keyed by "{scenario_id}:{job_identifier}" to avoid duplicate pollers when
# multiple tabs open the same job's status stream.
_active_pollers: dict[str, asyncio.Task[None]] = {}


class FinetuneLaunchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    approval_token: str
    force_retrain: bool = False
    training_data_s3_key: str
    validation_data_s3_key: str


class FinetuneLaunchResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_arn: str


class FinetuneStatusEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str
    output_model_arn: str | None = None
    failure_message: str | None = None
    creation_time: str | None = None
    last_modified_time: str | None = None
    job_name: str | None = None
    job_arn: str | None = None
    is_status_change: bool = False
    logged_at: str
    validation_status: str | None = None
    training_status: str | None = None


@router.post("/finetune/{scenario_id}/launch", response_model=FinetuneLaunchResponse)
def launch_finetune(
    request: FinetuneLaunchRequest,
    scenario: ScenarioConfig = Depends(get_enabled_scenario),
    settings: Settings = Depends(get_settings),
    session: boto3.Session = Depends(get_boto_session),
) -> FinetuneLaunchResponse:
    if request.approval_token != APPROVAL_TOKEN:
        raise HTTPException(status_code=403, detail="A valid typed approval token is required.")

    bucket = data_bucket_name(settings.project_suffix, settings.aws_region)
    finetune_client = FinetuneClient(project_suffix=settings.project_suffix, session=session)
    role_arn = bedrock_role_arn(session, settings.project_suffix)

    try:
        response = finetune_client.create_model_customization_job(
            scenario_id=scenario.id,
            base_model_id=scenario.base_model_id,
            role_arn=role_arn,
            training_data_s3_uri=f"s3://{bucket}/{request.training_data_s3_key}",
            validation_data_s3_uri=f"s3://{bucket}/{request.validation_data_s3_key}",
            output_s3_uri=f"s3://{bucket}/output/{scenario.id}/",
            epochs=scenario.epochs,
            force_retrain=request.force_retrain,
            approval_token=request.approval_token if request.force_retrain else None,
        )
    except RetrainRefusedError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ClientError as exc:
        error_code = exc.response.get("Error", {}).get("Code", "")
        error_message = exc.response.get("Error", {}).get("Message", str(exc))
        if error_code == "ValidationException" and "job name is currently in use" in error_message:
            raise HTTPException(
                status_code=409,
                detail=(
                    f"A job named {finetune_client.job_name(scenario.id)!r} is already running "
                    "or already exists in Bedrock (likely launched earlier from the CLI). "
                    "Use 'Skip to status' instead of relaunching."
                ),
            ) from exc
        raise HTTPException(status_code=502, detail=f"{error_code}: {error_message}") from exc

    return FinetuneLaunchResponse(job_arn=response["jobArn"])


async def _poll_and_persist(
    scenario_id: str, finetune_client: FinetuneClient, job_identifier: str
) -> None:
    """Runs for the lifetime of the job, independent of any SSE connection.

    Queries Bedrock every STATUS_POLL_SECONDS so real status changes are
    detected and persisted within ~10s, but only writes a "heartbeat" row to
    the log every HEARTBEAT_INTERVAL_SECONDS while status is unchanged, to
    keep the persisted history readable over a multi-hour job.
    """
    history = read_events(scenario_id)
    last_fingerprint = (
        (
            history[-1]["status"],
            history[-1].get("validation_status"),
            history[-1].get("training_status"),
        )
        if history
        else None
    )
    # A restart loses the in-process heartbeat clock; treat "just restarted" as
    # already due for a heartbeat so a real change is never missed, but seed
    # last_fingerprint from disk so we don't log a false "status changed" the
    # moment the new poller takes over an unchanged, still-running job.
    last_persisted_monotonic: float | None = None
    while True:
        try:
            job = await asyncio.to_thread(
                finetune_client.get_model_customization_job, job_identifier
            )
        except ClientError as exc:
            error_code = exc.response.get("Error", {}).get("Code", "")
            append_event(
                scenario_id,
                FinetuneStatusEvent(
                    status="Unknown",
                    failure_message=f"Could not query job status: {error_code}",
                    job_name=job_identifier,
                    logged_at=datetime.now(UTC).isoformat(),
                    is_status_change=True,
                ).model_dump(),
            )
            return

        status = job["status"]
        status_details = job.get("statusDetails") or {}
        validation_status = (status_details.get("validationDetails") or {}).get("status")
        training_status = (status_details.get("trainingDetails") or {}).get("status")
        # Sub-phase transitions (e.g. Training NotStarted -> InProgress) are the
        # real signal for a multi-hour job — the top-level status stays
        # "InProgress" the whole time, so fingerprinting on sub-phases too is
        # what actually catches meaningful progress.
        fingerprint = (status, validation_status, training_status)
        is_change = fingerprint != last_fingerprint
        terminal = status in TERMINAL_STATUSES
        due_for_heartbeat = (
            last_persisted_monotonic is None
            or (time.monotonic() - last_persisted_monotonic) >= HEARTBEAT_INTERVAL_SECONDS
        )

        if is_change or due_for_heartbeat or terminal:
            creation_time = job.get("creationTime")
            last_modified_time = job.get("lastModifiedTime")
            event = FinetuneStatusEvent(
                status=status,
                output_model_arn=job.get("outputModelArn"),
                failure_message=job.get("failureMessage"),
                creation_time=creation_time.isoformat() if creation_time else None,
                last_modified_time=last_modified_time.isoformat() if last_modified_time else None,
                job_name=job_identifier,
                job_arn=job.get("jobArn"),
                is_status_change=is_change,
                logged_at=datetime.now(UTC).isoformat(),
                validation_status=validation_status,
                training_status=training_status,
            )
            append_event(scenario_id, event.model_dump())
            last_persisted_monotonic = time.monotonic()

        last_fingerprint = fingerprint
        if terminal:
            return
        await asyncio.sleep(STATUS_POLL_SECONDS)


def _ensure_poller_running(
    scenario_id: str, finetune_client: FinetuneClient, job_identifier: str
) -> None:
    key = f"{scenario_id}:{job_identifier}"
    existing = _active_pollers.get(key)
    if existing is None or existing.done():
        _active_pollers[key] = asyncio.create_task(
            _poll_and_persist(scenario_id, finetune_client, job_identifier)
        )


async def _status_event_stream(scenario_id: str) -> AsyncGenerator[str, None]:
    persisted = read_events(scenario_id)
    for event in persisted:
        yield f"data: {json.dumps(event)}\n\n"
        if event.get("status") in TERMINAL_STATUSES:
            return

    last_count = len(persisted)
    while True:
        await asyncio.sleep(STREAM_TAIL_POLL_SECONDS)
        current = read_events(scenario_id)
        if len(current) > last_count:
            for event in current[last_count:]:
                yield f"data: {json.dumps(event)}\n\n"
                if event.get("status") in TERMINAL_STATUSES:
                    return
            last_count = len(current)


@router.get("/finetune/{scenario_id}/status")
async def stream_finetune_status(
    scenario: ScenarioConfig = Depends(get_enabled_scenario),
    settings: Settings = Depends(get_settings),
    session: boto3.Session = Depends(get_boto_session),
) -> StreamingResponse:
    finetune_client = FinetuneClient(project_suffix=settings.project_suffix, session=session)
    # An explicit override still wins. The fallback resolves the newest real job for the
    # scenario rather than rebuilding the canonical name: Bedrock reserves job names
    # permanently, so the canonical name may belong to no job at all — which surfaced in
    # the UI as a completed job reporting status "Unknown".
    #
    # to_thread because resolving paginates Bedrock's job list, a blocking network call.
    # Awaiting it inline stalls the event loop for every other request, including /health,
    # for as long as the pagination takes.
    override = read_active_job_override(scenario.id)
    if override is not None:
        job_identifier = override
    else:
        job_identifier = await asyncio.to_thread(
            finetune_client.resolve_job_identifier, scenario.id
        )
    _ensure_poller_running(scenario.id, finetune_client, job_identifier)
    return StreamingResponse(
        _status_event_stream(scenario.id),
        media_type="text/event-stream",
    )
